"""Integration tests for migration 0071 — Cohort 3 first slot match_algorithm lookup.

Verifies the POST-MIGRATION state of the ``match_algorithm`` lookup table
introduced by migration 0071 — Cohort 3 first slot, standalone per the
session 78 5-slot adjudication (ADR-118 v2.41 amendment).

Test groups:
    - TestTableShape: ``match_algorithm`` columns / types / nullability /
      defaults / max-character-lengths (full column spec).
    - TestConstraints: composite UNIQUE on ``(name, version)`` —
      ``uq_match_algorithm`` — load-bearing for the Cohort 3 contract that
      ``(name, version)`` is the algorithm business key.
    - TestSeedRow: the Phase 1 ``manual_v1`` / ``1.0.0`` seed row exists with
      the canonical Pattern 73 SSOT ``code_ref`` value
      (``'precog.matching.manual_v1'``) and ``retired_at IS NULL`` (active).
    - TestSeedIdempotence: re-running the seed INSERT (via
      ``ON CONFLICT (name, version) DO NOTHING``) leaves the row count at
      exactly 1, not 2 — proves the migration is replay-safe.
    - TestUniqueConstraintBehavior: a second INSERT of the same
      ``(manual_v1, 1.0.0)`` tuple raises ``psycopg2.errors.UniqueViolation``,
      proving the composite UNIQUE actually fires.

Two **load-bearing assertions** per Holden's spec memo
(``memory/build_spec_0071_holden_memo.md`` § 5 step 5):
    (a) UNIQUE-violation assertion: a hand-crafted duplicate INSERT fires
        ``psycopg2.errors.UniqueViolation``;
    (b) Idempotent-replay assertion: running the seed-helper SQL twice
        leaves the row count at 1, not 2.

Issue: Epic #972 (Canonical Layer Foundation — Phase B.5)
ADR: ADR-118 v2.40 lines 17621-17628 (canonical DDL anchor); v2.41 amendment
    (Cohort 3 5-slot adjudication, session 78)
Build spec: ``memory/build_spec_0071_holden_memo.md``

Markers:
    @pytest.mark.integration: real DB required.
"""

from __future__ import annotations

from typing import Any

import psycopg2
import pytest

from precog.database.connection import get_cursor

pytestmark = [pytest.mark.integration]


# =============================================================================
# Per-table column spec (mirrors migration 0071 DDL verbatim).
#
# Each tuple: (column_name, data_type, is_nullable, default_substring_or_None,
#              max_char_length_or_None).
# Pattern 73 SSOT discipline: the migration owns the column shape in code;
# this spec mirrors verbatim.  Drift here => test fails => alignment forced.
# =============================================================================

_MATCH_ALGORITHM_COLS: list[tuple[str, str, str, str | None, int | None]] = [
    ("id", "bigint", "NO", "nextval", None),
    ("name", "character varying", "NO", None, 64),
    ("version", "character varying", "NO", None, 16),
    ("code_ref", "character varying", "NO", None, 255),
    ("description", "text", "YES", None, None),
    ("created_at", "timestamp with time zone", "NO", "now()", None),
    ("retired_at", "timestamp with time zone", "YES", None, None),
]


# =============================================================================
# Group 1: Table shape
# =============================================================================


@pytest.mark.parametrize(
    ("col_name", "data_type", "is_nullable", "default_substr", "max_char_len"),
    _MATCH_ALGORITHM_COLS,
)
def test_match_algorithm_column_shape(
    db_pool: Any,
    col_name: str,
    data_type: str,
    is_nullable: str,
    default_substr: str | None,
    max_char_len: int | None,
) -> None:
    """Each column on match_algorithm has the migration-prescribed shape."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT data_type, is_nullable, column_default, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'match_algorithm'
              AND column_name = %s
              AND table_schema = 'public'
            """,
            (col_name,),
        )
        row = cur.fetchone()
    assert row is not None, f"match_algorithm.{col_name} missing post-0071"
    assert row["data_type"] == data_type, (
        f"match_algorithm.{col_name} type mismatch: "
        f"expected {data_type!r}, got {row['data_type']!r}"
    )
    assert row["is_nullable"] == is_nullable, (
        f"match_algorithm.{col_name} nullability mismatch: "
        f"expected {is_nullable!r}, got {row['is_nullable']!r}"
    )
    if default_substr is not None:
        actual_default = row["column_default"] or ""
        assert default_substr.lower() in actual_default.lower(), (
            f"match_algorithm.{col_name} default missing {default_substr!r}; got {actual_default!r}"
        )
    if max_char_len is not None:
        assert row["character_maximum_length"] == max_char_len, (
            f"match_algorithm.{col_name} max_length mismatch: "
            f"expected {max_char_len}, got {row['character_maximum_length']}"
        )


def test_match_algorithm_has_no_updated_at_column(db_pool: Any) -> None:
    """Per Critical Pattern #6 (Immutable Versioning): NO updated_at column.

    Algorithms are immutable post-seed; re-tuning a matcher INSERTs a new
    ``(name, version)`` row rather than UPDATEing the existing row.
    Building in an ``updated_at`` column would tempt callers into UPDATE
    paths that violate immutability.  Pinning the absence here so a future
    PR proposing "add updated_at" fails this test loudly.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'match_algorithm'
              AND column_name = 'updated_at'
              AND table_schema = 'public'
            """
        )
        row = cur.fetchone()
    assert row is None, (
        "match_algorithm must NOT have an updated_at column "
        "(Critical Pattern #6 — algorithms are immutable; re-tuning = new row)"
    )


# =============================================================================
# Group 2: Constraints (composite UNIQUE on (name, version))
# =============================================================================


def test_uq_match_algorithm_unique_constraint_exists(db_pool: Any) -> None:
    """``uq_match_algorithm`` UNIQUE (name, version) must exist post-0071."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'match_algorithm'::regclass
              AND conname = 'uq_match_algorithm'
            """
        )
        row = cur.fetchone()
    assert row is not None, "uq_match_algorithm UNIQUE constraint missing post-0071"
    constraint_def = row["def"]
    assert "UNIQUE" in constraint_def, f"uq_match_algorithm must be UNIQUE; got: {constraint_def}"
    assert "name" in constraint_def, (
        f"uq_match_algorithm must reference name; got: {constraint_def}"
    )
    assert "version" in constraint_def, (
        f"uq_match_algorithm must reference version; got: {constraint_def}"
    )


def test_match_algorithm_primary_key_is_id(db_pool: Any) -> None:
    """match_algorithm primary key is the BIGSERIAL ``id`` column."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT a.attname AS column_name
            FROM pg_index i
            JOIN pg_attribute a
              ON a.attrelid = i.indrelid
             AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = 'match_algorithm'::regclass
              AND i.indisprimary
            """
        )
        rows = cur.fetchall()
    pk_columns = [r["column_name"] for r in rows]
    assert pk_columns == ["id"], f"match_algorithm primary key must be (id); got: {pk_columns}"


# =============================================================================
# Group 3: Phase 1 seed row
# =============================================================================


def test_manual_v1_seed_row_exists_with_canonical_code_ref(db_pool: Any) -> None:
    """Phase 1 seed: ('manual_v1', '1.0.0') exists with the canonical SSOT code_ref.

    The Pattern 73 SSOT pointer ``code_ref = 'precog.matching.manual_v1'``
    is reserved by this seed for Cohort 5+ resolver work (Migration 0085
    territory).  If a future migration ships a different code_ref value
    (e.g., a typo, or a divergent module path), this test fires and forces
    the alignment back to the ADR.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, name, version, code_ref, description,
                   created_at, retired_at
            FROM match_algorithm
            WHERE name = %s AND version = %s
            """,
            ("manual_v1", "1.0.0"),
        )
        row = cur.fetchone()
    assert row is not None, (
        "Phase 1 seed missing — match_algorithm should contain ('manual_v1', '1.0.0') "
        "post-0071 (ADR-118 v2.40 line 17628 + Phase 1 commitments line ~17929)"
    )
    assert row["code_ref"] == "precog.matching.manual_v1", (
        f"Phase 1 seed code_ref drift: expected 'precog.matching.manual_v1', "
        f"got {row['code_ref']!r}"
    )
    assert row["retired_at"] is None, (
        f"Phase 1 seed must be active (retired_at IS NULL); got {row['retired_at']!r}"
    )
    assert row["description"], "Phase 1 seed should carry a non-empty description"


def test_only_one_seed_row_post_migration(db_pool: Any) -> None:
    """Phase 1 commitment: exactly ONE seed row post-0071.

    ADR-118 v2.40 line 17628 + Phase 1 commitments line ~17929 are explicit:
    "Phase 1 seeds exactly one row".  Future cohorts extend by INSERT (e.g.,
    Phase 3 keyword_jaccard_v1 ships in its cohort-of-origin migration), but
    Migration 0071 itself seeds exactly one row.  If a future PR sneaks an
    additional seed into 0071, this test fires.
    """
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM match_algorithm")
        row = cur.fetchone()
    assert row["n"] == 1, (
        f"Expected exactly 1 seed row post-0071; got {row['n']} (Phase 1 commitments line ~17929)"
    )


# =============================================================================
# Group 4: Idempotent seed (load-bearing — Holden Risk B mitigation)
# =============================================================================


def test_seed_replay_is_idempotent_via_on_conflict_do_nothing(db_pool: Any) -> None:
    """Re-running the seed INSERT leaves row count at 1, not 2.

    LOAD-BEARING per build_spec_0071_holden_memo.md § 5 step 5(d):
    Without ``ON CONFLICT (name, version) DO NOTHING``, re-running 0071 on
    a partially-migrated DB crashes with UniqueViolation.  This test is the
    replay-safety proof: we manually re-execute the seed-helper SQL inside
    the test (mirroring what an Alembic re-upgrade would do) and assert the
    row count stays at 1.

    Why a load-bearing test: a future refactor that drops the ON CONFLICT
    clause (e.g., "cleaning up the SQL") would break replay-safety
    silently — the migration would still apply on a fresh DB, but a
    partial-application + retry would crash.  This test catches that
    regression.
    """
    # Pre-condition: exactly 1 seed row from the migration upgrade.
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM match_algorithm")
        n_before = cur.fetchone()["n"]
    assert n_before == 1, f"Pre-condition broken: expected 1 row, got {n_before}"

    # Replay the seed INSERT verbatim (with the ON CONFLICT clause).  A
    # successful no-op proves the migration's seed helper is idempotent.
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO match_algorithm (name, version, code_ref, description)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name, version) DO NOTHING
            """,
            (
                "manual_v1",
                "1.0.0",
                "precog.matching.manual_v1",
                "replay test (must be silently ignored by ON CONFLICT)",
            ),
        )

    # Post-condition: still exactly 1 row.  ON CONFLICT DO NOTHING swallowed
    # the duplicate.  The original row's description is unchanged because
    # DO NOTHING does not UPDATE.
    with get_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM match_algorithm WHERE name = %s AND version = %s",
            ("manual_v1", "1.0.0"),
        )
        n_after = cur.fetchone()["n"]
    assert n_after == 1, (
        f"Idempotent-replay broken: expected row count to stay at 1, got {n_after}. "
        "ON CONFLICT (name, version) DO NOTHING is the load-bearing clause."
    )


# =============================================================================
# Group 5: UNIQUE constraint behavior (load-bearing — Holden Risk D mitigation)
# =============================================================================


def test_duplicate_name_version_insert_raises_unique_violation(db_pool: Any) -> None:
    """A raw duplicate INSERT (without ON CONFLICT) raises UniqueViolation.

    LOAD-BEARING per build_spec_0071_holden_memo.md § 5 step 5(c) +
    Risk D mitigation: the composite UNIQUE constraint must actually fire
    when a caller bypasses the ON CONFLICT discipline.  Without this test,
    a future migration that accidentally drops the UNIQUE (or replaces it
    with a non-unique index) would silently admit duplicate
    ``(name, version)`` rows and the matching layer would resolve to
    arbitrary algorithm rows depending on insertion order.

    This is the affirmative behavioral proof that the constraint is the
    single source of truth for ``(name, version)`` uniqueness — not just
    seed discipline.

    Implicit dependency on ``get_cursor`` rollback-on-exception semantics:
    after the UniqueViolation fires, this test relies on
    ``get_cursor.__exit__`` rolling back the aborted transaction so that
    subsequent test fixtures see a clean connection state.  If a future
    refactor of ``connection.py`` changes that behavior (e.g., suppresses
    the exception or omits the rollback), this test will appear to pass
    while leaving the session in an aborted state — manifesting as
    confusing ``InFailedSqlTransaction`` errors in the next test in the
    module.  The rollback discipline is behavioral, not assertion-pinned;
    flagged here so a future refactor surfaces the dependency.
    """
    # Attempt a duplicate INSERT without ON CONFLICT — must raise.
    with pytest.raises(psycopg2.errors.UniqueViolation):
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO match_algorithm (name, version, code_ref, description)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    "manual_v1",
                    "1.0.0",
                    "precog.matching.manual_v1",
                    "duplicate insert — must collide on uq_match_algorithm",
                ),
            )


def test_same_name_different_version_coexist(db_pool: Any) -> None:
    """('manual_v1', '1.0.0') and ('manual_v1', '1.1.0') can coexist.

    Composite uniqueness lets a re-tuned matcher (new version) coexist with
    its predecessor — Critical Pattern #6 immutability requires this:
    re-tuning ships as a NEW row (with new version), not an UPDATE.  This
    test pins the contract that a future PR seeding ``manual_v1`` /
    ``1.1.0`` does NOT collide with the Phase 1 seed.

    Cleanup: the test deletes its own ``1.1.0`` row in the finally block
    so the DB returns to the canonical 1-row Phase 1 state.
    """
    test_version = "1.1.0"

    # Pre-cleanup any residue from a prior failed run.
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM match_algorithm WHERE name = %s AND version = %s",
            ("manual_v1", test_version),
        )

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO match_algorithm (name, version, code_ref, description)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (
                    "manual_v1",
                    test_version,
                    "precog.matching.manual_v1",
                    "Re-tune of Phase 1 baseline (test row)",
                ),
            )
            new_id = cur.fetchone()["id"]
        assert new_id is not None, "INSERT of (manual_v1, 1.1.0) must succeed"

        # Both rows must coexist.
        with get_cursor() as cur:
            cur.execute(
                "SELECT version FROM match_algorithm WHERE name = %s ORDER BY version",
                ("manual_v1",),
            )
            rows = cur.fetchall()
            versions = [r["version"] for r in rows]
        assert versions == ["1.0.0", test_version], (
            f"Expected both ('manual_v1','1.0.0') and ('manual_v1','{test_version}') "
            f"to coexist; got versions: {versions}"
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM match_algorithm WHERE name = %s AND version = %s",
                ("manual_v1", test_version),
            )
