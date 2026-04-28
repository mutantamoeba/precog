"""Integration tests for migration 0075 — Cohort 3 fifth slot observation_source lookup.

Verifies the POST-MIGRATION state of the ``observation_source`` lookup
table introduced by migration 0075 — Cohort 3 fifth slot, the
observation-pipeline parent lookup that slot 0076+
(``canonical_observations`` partitioned fact table +
``canonical_event_phase_log``) FK into.  Per session-78 5-slot
adjudication (ADR-118 v2.41 amendment) + session-81 PM build spec
(``memory/build_spec_0075_pm_memo.md``).

Test groups:
    - Column shape: per-column type / nullability / default / max-length
      with mirror-symmetric f-string assertion messages from day 1
      (#1085 finding #4 — slot 0075 inherits the lesson).
    - UNIQUE constraint behavior: a duplicate ``source_key`` INSERT raises
      ``psycopg2.errors.UniqueViolation`` (with tuple-form per
      slot-0072+0073 sibling-test pattern accepting either UniqueViolation
      or generic IntegrityError as a defense-in-depth fallback).
    - Phase 1 seeds: all three rows ('espn', 'kalshi', 'manual') exist
      with the canonical source_kind values (Pattern 73 SSOT real-guard
      via ``PHASE_1_SOURCE_KEYS`` import).
    - ``created_at`` default fires when INSERTing without explicit value.
    - ``retired_at`` is NULL by default (active source).
    - ``authoritative_for JSONB`` accepts arrays and round-trips.
    - Index existence: PK + UNIQUE on ``source_key``.
    - **Pattern 81 carve-out pin**: zero CHECK constraints on the table
      (load-bearing — defends against a future PR proposing "add CHECK on
      source_kind" against ADR text rather than against silence).

Pattern 73 SSOT discipline test:
    - Imports ``PHASE_1_SOURCE_KEYS`` from constants.py and asserts each
      value round-trips through the seeded rows.  Ensures the Python
      constant and the seeded lookup-table rows don't drift.

Issue: Epic #972 (Canonical Layer Foundation — Phase B.5), #1058,
    #1085 (slot-0073/0075 polish-item inheritance — mirror-symmetric
    f-strings)
ADR: ADR-118 v2.40 lines 17785-17791 (canonical DDL anchor) + line 18006
    (canonical seed list); v2.41 amendment (Cohort 3 5-slot adjudication,
    session 78)
Build spec: ``memory/build_spec_0075_pm_memo.md``

Markers:
    @pytest.mark.integration: real DB required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import psycopg2
import psycopg2.errors
import pytest

from precog.database.connection import get_cursor
from precog.database.constants import PHASE_1_SOURCE_KEYS

pytestmark = [pytest.mark.integration]


# =============================================================================
# Per-column shape spec (mirrors migration 0075 DDL verbatim).
#
# Each tuple: (column_name, data_type, is_nullable, default_substring_or_None,
#              max_char_length_or_None).
# Pattern 73 SSOT discipline: the migration owns the column shape in code;
# this spec mirrors verbatim.  Drift here => test fails => alignment forced.
# Mirror-symmetric assertion messages per #1085 finding #4.
# =============================================================================

_OBSERVATION_SOURCE_COLS: list[tuple[str, str, str, str | None, int | None]] = [
    ("id", "bigint", "NO", "nextval", None),
    ("source_key", "character varying", "NO", None, 64),
    ("source_kind", "character varying", "NO", None, 32),
    ("authoritative_for", "jsonb", "YES", None, None),
    ("created_at", "timestamp with time zone", "NO", "now()", None),
    ("retired_at", "timestamp with time zone", "YES", None, None),
]


# =============================================================================
# Group 1: Column shape
# =============================================================================


@pytest.mark.parametrize(
    ("col_name", "data_type", "is_nullable", "default_substr", "max_char_len"),
    _OBSERVATION_SOURCE_COLS,
)
def test_observation_source_column_shape(
    db_pool: Any,
    col_name: str,
    data_type: str,
    is_nullable: str,
    default_substr: str | None,
    max_char_len: int | None,
) -> None:
    """Each column on observation_source has the migration-prescribed shape."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT data_type, is_nullable, column_default, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'observation_source'
              AND column_name = %s
              AND table_schema = 'public'
            """,
            (col_name,),
        )
        row = cur.fetchone()
    assert row is not None, f"observation_source.{col_name} missing post-0075"
    assert row["data_type"] == data_type, (
        f"observation_source.{col_name} type mismatch: "
        f"expected {data_type!r}, got {row['data_type']!r}"
    )
    assert row["is_nullable"] == is_nullable, (
        f"observation_source.{col_name} nullability mismatch: "
        f"expected {is_nullable!r}, got {row['is_nullable']!r}"
    )
    if default_substr is not None:
        actual_default = row["column_default"] or ""
        assert default_substr.lower() in actual_default.lower(), (
            f"observation_source.{col_name} default missing {default_substr!r}; "
            f"got {actual_default!r}"
        )
    if max_char_len is not None:
        assert row["character_maximum_length"] == max_char_len, (
            f"observation_source.{col_name} max_length mismatch: "
            f"expected {max_char_len}, got {row['character_maximum_length']}"
        )


def test_observation_source_has_no_updated_at_column(db_pool: Any) -> None:
    """Per Critical Pattern #6 (Immutable Versioning): NO updated_at column.

    Sources are immutable post-seed; re-categorizing a source INSERTs a
    new ``source_key`` row + retires the old (set ``retired_at = now()``)
    rather than UPDATEing the existing row.  Building in an
    ``updated_at`` column would tempt callers into UPDATE paths that
    violate immutability.  Pinning the absence here so a future PR
    proposing "add updated_at" fails this test loudly.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'observation_source'
              AND column_name = 'updated_at'
              AND table_schema = 'public'
            """
        )
        row = cur.fetchone()
    assert row is None, (
        "observation_source must NOT have an updated_at column "
        "(Critical Pattern #6 — sources are immutable; re-categorize = new row)"
    )


# =============================================================================
# Group 2: UNIQUE constraint behavior
# =============================================================================


def test_observation_source_unique_source_key_fires(db_pool: Any) -> None:
    """A duplicate ``source_key`` INSERT raises UniqueViolation.

    LOAD-BEARING: the single-column UNIQUE constraint must actually fire
    when a caller bypasses the ON CONFLICT discipline.  Without this
    test, a future migration that accidentally drops the UNIQUE (or
    replaces it with a non-unique index) would silently admit duplicate
    ``source_key`` rows and the canonical_observations FK resolution
    would resolve to arbitrary rows depending on insertion order.

    Tuple-form ``pytest.raises((UniqueViolation, IntegrityError))`` per
    slot-0072+0073 sibling-test pattern: psycopg2 may surface the
    violation as either the specific ``UniqueViolation`` subclass or
    the generic ``IntegrityError`` parent depending on driver path.

    Implicit dependency on ``get_cursor`` rollback-on-exception
    semantics: after the violation fires, this test relies on
    ``get_cursor.__exit__`` rolling back the aborted transaction so
    subsequent test fixtures see a clean connection state.
    """
    # Attempt a duplicate INSERT of 'espn' (already seeded) without
    # ON CONFLICT — must raise.
    with pytest.raises((psycopg2.errors.UniqueViolation, psycopg2.errors.IntegrityError)):
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO observation_source (source_key, source_kind, authoritative_for)
                VALUES (%s, %s, %s)
                """,
                ("espn", "api", None),
            )


# =============================================================================
# Group 3: Phase 1 seed rows (Pattern 73 SSOT real-guard)
# =============================================================================


def test_observation_source_phase_1_seeds_present(db_pool: Any) -> None:
    """Phase 1 seeds: all three rows ('espn', 'kalshi', 'manual') exist.

    Pattern 73 SSOT real-guard: imports ``PHASE_1_SOURCE_KEYS`` from
    ``constants.py`` and asserts every value round-trips through the
    seeded lookup-table rows.  This is the #1085-finding-#2 strengthening
    of side-effect-only constant imports — real-guard usage turns a
    documentation cite into an executable contract.

    If a future PR adds a new source to ``PHASE_1_SOURCE_KEYS`` without
    updating the migration seed list (or vice versa), this test fires
    and forces alignment.

    ADR-118 line 18006 binding: "Seeds: match_algorithm(manual_v1),
    observation_source(espn, kalshi, manual)".  Phase 1 seeds exactly
    these three rows.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT source_key, source_kind, authoritative_for, retired_at
            FROM observation_source
            WHERE source_key = ANY(%s)
            ORDER BY source_key
            """,
            (list(PHASE_1_SOURCE_KEYS),),
        )
        rows = cur.fetchall()
    seen_keys = [r["source_key"] for r in rows]
    expected_keys = sorted(PHASE_1_SOURCE_KEYS)
    assert seen_keys == expected_keys, (
        f"Phase 1 seed drift: expected source_keys {expected_keys}, got {seen_keys}. "
        "PHASE_1_SOURCE_KEYS (constants.py) and the migration seed list must stay aligned."
    )

    # Glokta P1 #2 (slot-0071-precedent gap): assert exact-row-count over the
    # whole table, not just the named-key subset.  Without this pin, a future
    # PR that sneaks a 4th seed inline into _OBSERVATION_SOURCE_SEED would
    # not be caught — the named-key subset assertion above would still pass.
    # Phase 3+ sources MUST extend via cohort-of-origin migrations, not via
    # inline edits to slot 0075's seed list.  Mirror of slot 0071's
    # `test_match_algorithm_seed_count_is_exactly_one`.
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM observation_source")
        count_row = cur.fetchone()
    assert count_row is not None, "COUNT(*) query must return a row"
    assert count_row["n"] == 3, (
        f"observation_source seed-count drift: expected exactly 3 Phase 1 rows "
        f"('espn'/'kalshi'/'manual'), got {count_row['n']}.  Phase 3+ sources "
        "(noaa/bls/fivethirtyeight) MUST extend via cohort-of-origin migrations, "
        "NOT via inline edits to slot 0075's _OBSERVATION_SOURCE_SEED list."
    )

    # Every seed row must be active (retired_at IS NULL) at Phase 1.
    for r in rows:
        assert r["retired_at"] is None, (
            f"Phase 1 seed {r['source_key']!r} must be active (retired_at IS NULL); "
            f"got {r['retired_at']!r}"
        )

    # Per build spec § 4: 'espn' and 'kalshi' have source_kind='api',
    # 'manual' has source_kind='manual'.  Pin the canonical mapping.
    expected_kinds = {"espn": "api", "kalshi": "api", "manual": "manual"}
    for r in rows:
        assert r["source_kind"] == expected_kinds[r["source_key"]], (
            f"Phase 1 seed {r['source_key']!r} source_kind drift: "
            f"expected {expected_kinds[r['source_key']]!r}, got {r['source_kind']!r}"
        )


def test_observation_source_seed_replay_is_idempotent_via_on_conflict_do_nothing(
    db_pool: Any,
) -> None:
    """Re-running the seed INSERT leaves row count at 3, not 6.

    **LOAD-BEARING per build spec § 4 + Pattern 67 idempotency discipline.**
    Without ``ON CONFLICT (source_key) DO NOTHING``, re-running migration 0075
    on a partially-migrated DB would crash with UniqueViolation.  This test
    is the replay-safety proof: we manually re-execute the seed-helper SQL
    inside the test (mirroring what an Alembic re-upgrade would do) and
    assert the row count stays at 3.

    Why a load-bearing test (Glokta P1 finding, session 81): a future
    refactor that drops the ``ON CONFLICT`` clause (e.g., "cleaning up the
    SQL") would break replay-safety silently — the migration would still
    apply on a fresh DB, but a partial-application + retry would crash.
    This test catches that regression.

    Mirrors slot 0071's
    ``test_seed_replay_is_idempotent_via_on_conflict_do_nothing`` — the
    Pattern 67 SSOT enforcement test pattern across Cohort 3 lookup tables.
    """
    # Pre-condition: exactly 3 seed rows from the migration upgrade.
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM observation_source")
        n_before = cur.fetchone()["n"]
    assert n_before == 3, f"Pre-condition broken: expected 3 rows, got {n_before}"

    # Replay the seed INSERTs verbatim (with the ON CONFLICT clause).  A
    # successful no-op for all 3 rows proves the migration's seed helper is
    # idempotent — Pattern 67 in action.
    seed_rows = [
        ("espn", "api", None),
        ("kalshi", "api", None),
        ("manual", "manual", None),
    ]
    with get_cursor(commit=True) as cur:
        for source_key, source_kind, authoritative_for in seed_rows:
            cur.execute(
                """
                INSERT INTO observation_source (source_key, source_kind, authoritative_for)
                VALUES (%s, %s, %s)
                ON CONFLICT (source_key) DO NOTHING
                """,
                (source_key, source_kind, authoritative_for),
            )

    # Post-condition: still exactly 3 rows.  ON CONFLICT DO NOTHING swallowed
    # all 3 duplicates.  The original rows are unchanged because DO NOTHING
    # does not UPDATE.
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM observation_source")
        n_after = cur.fetchone()["n"]
    assert n_after == 3, (
        f"Idempotent-replay broken: expected row count to stay at 3, got {n_after}. "
        "ON CONFLICT (source_key) DO NOTHING is the load-bearing clause; if it "
        "was dropped or its column-set changed, replay-safety silently breaks."
    )


# =============================================================================
# Group 4: created_at default fires
# =============================================================================


def test_observation_source_created_at_default_fires(db_pool: Any) -> None:
    """INSERT without explicit ``created_at`` populates with now()-anchored timestamp.

    Pins the v2.42 sub-amendment A audit-column convention: the
    ``DEFAULT now()`` clause must fire when a caller omits
    ``created_at`` from the INSERT column list.  Without this test, a
    future migration that drops the DEFAULT would let callers INSERT
    rows with NULL created_at — violating the NOT NULL constraint at
    runtime rather than at schema-time, surfacing as IntegrityError on
    every INSERT path that doesn't explicitly populate created_at.
    """
    test_key = "test_default_fires"

    # Pre-cleanup any residue from a prior failed run.
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM observation_source WHERE source_key = %s",
            (test_key,),
        )

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO observation_source (source_key, source_kind)
                VALUES (%s, %s)
                RETURNING created_at
                """,
                (test_key, "manual"),
            )
            row = cur.fetchone()
        assert row is not None, "INSERT into observation_source must succeed"
        assert row["created_at"] is not None, (
            f"observation_source.created_at default failed to fire — "
            f"got NULL for {test_key!r}; DEFAULT now() clause must populate the column"
        )

        # Ripley P1 (false-pass-hunt): IS NOT NULL alone would silently pass
        # if DEFAULT shifted to epoch (1970), '-infinity', or any other
        # non-now() timestamp.  Assert freshness: the default must produce a
        # timestamp within ~60 seconds of the current wall-clock time.
        now = datetime.now(UTC)
        delta_seconds = abs((now - row["created_at"]).total_seconds())
        assert delta_seconds < 60, (
            f"observation_source.created_at DEFAULT now() should populate "
            f"a timestamp near the current wall-clock; got {row['created_at']!r}, "
            f"expected within 60s of {now!r} (delta={delta_seconds:.1f}s).  "
            "An epoch-default or -infinity-default bug would silently pass an "
            "IS-NOT-NULL-only assertion; this freshness check defends against that."
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM observation_source WHERE source_key = %s",
                (test_key,),
            )


# =============================================================================
# Group 5: retired_at NULL by default
# =============================================================================


def test_observation_source_retired_at_null_by_default(db_pool: Any) -> None:
    """A fresh INSERT leaves ``retired_at`` NULL (active source).

    Active sources have ``retired_at IS NULL``; retirement is a deliberate
    UPDATE (set ``retired_at = now()``) per Critical Pattern #6
    semantics.  This test pins the contract that a freshly-inserted
    source defaults to active without requiring the caller to explicitly
    pass NULL.
    """
    test_key = "test_retired_at_null"

    # Pre-cleanup any residue from a prior failed run.
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM observation_source WHERE source_key = %s",
            (test_key,),
        )

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO observation_source (source_key, source_kind)
                VALUES (%s, %s)
                RETURNING retired_at
                """,
                (test_key, "manual"),
            )
            row = cur.fetchone()
        assert row is not None, "INSERT into observation_source must succeed"
        assert row["retired_at"] is None, (
            f"observation_source.retired_at must default to NULL for active sources; "
            f"got {row['retired_at']!r} for {test_key!r}"
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM observation_source WHERE source_key = %s",
                (test_key,),
            )


# =============================================================================
# Group 6: authoritative_for JSONB round-trip
# =============================================================================


def test_observation_source_authoritative_for_accepts_array(db_pool: Any) -> None:
    """``authoritative_for JSONB`` accepts arrays and round-trips correctly.

    Phase 1 seeds set ``authoritative_for`` to NULL because
    ``canonical_observations.observation_kind`` vocabulary doesn't land
    until slot 0076+.  This test pins the JSONB column shape by
    INSERTing a JSON array (e.g., ``["sport_game_state"]``) and
    asserting it round-trips intact, so a future slot-0076+ migration
    that backfills ``authoritative_for`` for ESPN / Kalshi has a
    behavioral pin proving the column accepts array shapes.
    """
    test_key = "test_jsonb_array"

    # Pre-cleanup any residue from a prior failed run.
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM observation_source WHERE source_key = %s",
            (test_key,),
        )

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO observation_source (source_key, source_kind, authoritative_for)
                VALUES (%s, %s, %s::jsonb)
                RETURNING authoritative_for
                """,
                (test_key, "api", '["sport_game_state", "market_snapshot"]'),
            )
            row = cur.fetchone()
        assert row is not None, "INSERT with JSONB array must succeed"
        assert row["authoritative_for"] == ["sport_game_state", "market_snapshot"], (
            f"observation_source.authoritative_for JSONB round-trip failed: "
            f"expected ['sport_game_state', 'market_snapshot'], "
            f"got {row['authoritative_for']!r}"
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM observation_source WHERE source_key = %s",
                (test_key,),
            )


# =============================================================================
# Group 7: Index existence (PK + UNIQUE)
# =============================================================================


def test_observation_source_indexes_exist(db_pool: Any) -> None:
    """PK and ``uq_observation_source_key`` UNIQUE-backing indexes both exist.

    Postgres backs UNIQUE constraints with implicit btree indexes; this
    test queries ``pg_indexes`` to verify both the PK index and the
    UNIQUE constraint's underlying index are present and named per the
    migration's ``CONSTRAINT uq_observation_source_key`` clause.

    Without these indexes, FK resolution from canonical_observations
    (slot 0076+) would table-scan ``observation_source`` on every join
    — pinning their existence prevents a future migration from dropping
    them silently.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'observation_source'
            ORDER BY indexname
            """
        )
        rows = cur.fetchall()
    index_names = [r["indexname"] for r in rows]

    # PK index name follows Postgres convention: <tablename>_pkey
    assert "observation_source_pkey" in index_names, (
        f"observation_source PK index 'observation_source_pkey' missing post-0075; "
        f"got indexes: {index_names}"
    )
    # UNIQUE constraint name from the migration DDL
    assert "uq_observation_source_key" in index_names, (
        f"observation_source UNIQUE-backing index 'uq_observation_source_key' "
        f"missing post-0075; got indexes: {index_names}"
    )


# =============================================================================
# Group 8: No CHECK constraints (Pattern 81 carve-out — LOAD-BEARING)
# =============================================================================


def test_observation_source_no_check_constraints(db_pool: Any) -> None:
    """``observation_source`` has ZERO CHECK constraints (Pattern 81 carve-out).

    LOAD-BEARING per build spec § 6 test #8: ``source_key`` and
    ``source_kind`` are intentionally OPEN ENUMs encoded as lookup-table
    rows (the ``observation_source`` table itself is the canonical
    store); adding a CHECK would defeat Pattern 81 by forcing every new
    source through a schema migration rather than a seed insert.

    Pinning this absence here so a future PR proposing "add CHECK on
    source_kind" argues against ADR-118 + Pattern 81 + this test rather
    than against silence.

    Same Pattern 81 shape as Migration 0071 ``match_algorithm`` (also
    zero CHECK constraints by Pattern 81 design).  Different from
    Migrations 0072 (``link_state``) and 0073 (``action`` + ``confidence``)
    which DO have CHECK constraints because their state vocabularies are
    closed-enum-with-code-branches per Pattern 81 § "When NOT to Apply".
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = 'observation_source'::regclass
              AND contype = 'c'
            """
        )
        rows = cur.fetchall()
    check_constraints = [r["conname"] for r in rows]
    assert check_constraints == [], (
        f"observation_source must have ZERO CHECK constraints "
        f"(Pattern 81 lookup-not-CHECK carve-out — source_key + source_kind are "
        f"open enums encoded as lookup-table rows, not CHECK-enforced); "
        f"got CHECK constraints: {check_constraints}"
    )
