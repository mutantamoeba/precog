"""Integration tests for migration 0068 -- Cohort 1B canonical entity foundation.

Verifies the POST-MIGRATION state of the four canonical-entity tables
introduced by migration 0068 -- ``canonical_entity_kinds``,
``canonical_entity``, ``canonical_participant_roles``, and
``canonical_event_participants`` -- the lookup-table seed rows (12 entity_kinds
+ 10 participant_roles), and the **CONSTRAINT TRIGGER** that enforces the
polymorphic typed back-ref invariant (``entity_kind='team' => ref_team_id NOT NULL``).

Test groups:
    - TestTableShapes: each of the 4 tables exists with the expected
      columns / types / nullability / defaults.
    - TestSeedRows: the 12 entity_kinds + 10 participant_roles are seeded
      verbatim per ADR-118 V2.38 decisions #1 + #4.
    - TestConstraintTrigger: **the highest-value gap** -- the
      ``trg_canonical_entity_team_backref`` CONSTRAINT TRIGGER body is
      exercised against:
        * INSERT entity_kind='team' + ref_team_id=NULL -> raises
        * INSERT entity_kind='team' + valid team_id -> succeeds
        * INSERT entity_kind='fighter' + ref_team_id=NULL -> succeeds (skip path)
        * UPDATE entity_kind_id -> 'team' on ref_team_id=NULL row -> raises
    - TestIndexes: 6 FK-column indexes (4 full + 2 partial WHERE).

Issue: #1012
Epic: #972 (Canonical Layer Foundation -- Phase B.5)

Markers:
    @pytest.mark.integration: real DB required.
"""

from __future__ import annotations

import uuid
from typing import Any

import psycopg2
import pytest

from precog.database.connection import get_cursor

pytestmark = [pytest.mark.integration]


# =============================================================================
# Per-table column spec (mirrors migration 0068 DDL verbatim).
#
# Each tuple: (column_name, data_type, is_nullable, default_substring_or_None).
# =============================================================================

_ENTITY_KINDS_COLS: list[tuple[str, str, str, str | None]] = [
    ("id", "integer", "NO", "nextval"),
    ("entity_kind", "text", "NO", None),
    ("description", "text", "YES", None),
    ("created_at", "timestamp with time zone", "NO", "now()"),
]

_ENTITY_COLS: list[tuple[str, str, str, str | None]] = [
    ("id", "bigint", "NO", "nextval"),
    ("entity_kind_id", "integer", "NO", None),
    ("entity_key", "text", "NO", None),
    ("display_name", "text", "NO", None),
    ("ref_team_id", "integer", "YES", None),
    ("metadata", "jsonb", "YES", None),
    ("created_at", "timestamp with time zone", "NO", "now()"),
]

_PARTICIPANT_ROLES_COLS: list[tuple[str, str, str, str | None]] = [
    ("id", "integer", "NO", "nextval"),
    ("domain_id", "integer", "YES", None),
    ("role", "text", "NO", None),
    ("description", "text", "YES", None),
    ("created_at", "timestamp with time zone", "NO", "now()"),
]

_EVENT_PARTICIPANTS_COLS: list[tuple[str, str, str, str | None]] = [
    ("id", "bigint", "NO", "nextval"),
    ("canonical_event_id", "bigint", "NO", None),
    ("entity_id", "bigint", "NO", None),
    ("role_id", "integer", "NO", None),
    ("sequence_number", "integer", "NO", None),
    ("created_at", "timestamp with time zone", "NO", "now()"),
]

_TABLE_SPEC: list[tuple[str, list[tuple[str, str, str, str | None]]]] = [
    ("canonical_entity_kinds", _ENTITY_KINDS_COLS),
    ("canonical_entity", _ENTITY_COLS),
    ("canonical_participant_roles", _PARTICIPANT_ROLES_COLS),
    ("canonical_event_participants", _EVENT_PARTICIPANTS_COLS),
]


# Expected seed rows verbatim from migration ``_ENTITY_KIND_SEED`` /
# ``_PARTICIPANT_ROLE_SEED``.
_EXPECTED_ENTITY_KINDS: list[str] = [
    "team",
    "fighter",
    "candidate",
    "storm",
    "company",
    "location",
    "person",
    "product",
    "country",
    "organization",
    "commodity",
    "media",
]

_EXPECTED_PARTICIPANT_ROLES: list[tuple[str, str]] = [
    ("sports", "home"),
    ("sports", "away"),
    ("fighting", "fighter_a"),
    ("fighting", "fighter_b"),
    ("politics", "candidate"),
    ("politics", "moderator"),
    ("weather", "affected_location"),
    ("entertainment", "nominee"),
    ("entertainment", "winner"),
    ("entertainment", "host"),
]


# Expected indexes per migration upgrade() body (PK / UNIQUE indexes excluded).
# (table, indexname, must_be_unique, partial_predicate_or_None).
_EXPECTED_INDEXES: list[tuple[str, str, bool, str | None]] = [
    ("canonical_entity", "idx_canonical_entity_entity_kind_id", False, None),
    (
        "canonical_entity",
        "idx_canonical_entity_ref_team_id",
        False,
        "ref_team_id IS NOT NULL",
    ),
    (
        "canonical_participant_roles",
        "idx_canonical_participant_roles_domain_id",
        False,
        "domain_id IS NOT NULL",
    ),
    (
        "canonical_event_participants",
        "idx_canonical_event_participants_canonical_event_id",
        False,
        None,
    ),
    (
        "canonical_event_participants",
        "idx_canonical_event_participants_entity_id",
        False,
        None,
    ),
    (
        "canonical_event_participants",
        "idx_canonical_event_participants_role_id",
        False,
        None,
    ),
]


# =============================================================================
# Group 1: Table shapes
# =============================================================================


@pytest.mark.parametrize(("table", "col_spec"), _TABLE_SPEC)
def test_table_column_shape(
    db_pool: Any,
    table: str,
    col_spec: list[tuple[str, str, str, str | None]],
) -> None:
    """Each column on each table has the migration-prescribed type / nullability / default."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s
              AND table_schema = 'public'
            ORDER BY ordinal_position
            """,
            (table,),
        )
        rows = cur.fetchall()
    actual = {r["column_name"]: r for r in rows}
    expected_names = {c[0] for c in col_spec}
    assert expected_names.issubset(set(actual.keys())), (
        f"{table}: missing columns. expected={expected_names!r}, got={set(actual.keys())!r}"
    )

    for col_name, data_type, is_nullable, default_substr in col_spec:
        row = actual[col_name]
        assert row["data_type"] == data_type, (
            f"{table}.{col_name} type mismatch: expected {data_type!r}, got {row['data_type']!r}"
        )
        assert row["is_nullable"] == is_nullable, (
            f"{table}.{col_name} nullability mismatch: "
            f"expected {is_nullable!r}, got {row['is_nullable']!r}"
        )
        if default_substr is not None:
            actual_default = row["column_default"] or ""
            assert default_substr.lower() in actual_default.lower(), (
                f"{table}.{col_name} default missing {default_substr!r}; got {actual_default!r}"
            )


def test_canonical_event_participants_sequence_number_has_no_default(
    db_pool: Any,
) -> None:
    """``sequence_number`` has NO default per ADR-118 V2.38 decision #6 / Glokta carry-forward #5.

    Forces callers to reason about sequence explicitly (the 10-candidate
    election case is the motivating example).
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT column_default
            FROM information_schema.columns
            WHERE table_name = 'canonical_event_participants'
              AND column_name = 'sequence_number'
              AND table_schema = 'public'
            """
        )
        row = cur.fetchone()
    assert row is not None, "canonical_event_participants.sequence_number must exist"
    assert row["column_default"] is None, (
        f"sequence_number must have NO default (Glokta carry-forward #5); "
        f"got {row['column_default']!r}"
    )


# =============================================================================
# Group 2: Seed rows (12 entity_kinds + 10 participant_roles)
# =============================================================================


def test_canonical_entity_kinds_has_all_seed_rows(db_pool: Any) -> None:
    """All 12 base entity_kinds seeded per ADR-118 V2.38 decision #1."""
    with get_cursor() as cur:
        cur.execute("SELECT entity_kind FROM canonical_entity_kinds ORDER BY id")
        rows = cur.fetchall()
    actual = [r["entity_kind"] for r in rows]
    for expected_kind in _EXPECTED_ENTITY_KINDS:
        assert expected_kind in actual, f"entity_kind {expected_kind!r} missing; got {actual!r}"
    assert len(actual) == len(_EXPECTED_ENTITY_KINDS), (
        f"canonical_entity_kinds row count drifted; expected {len(_EXPECTED_ENTITY_KINDS)}, "
        f"got {len(actual)}: {actual!r}"
    )


def test_canonical_participant_roles_has_all_seed_rows(db_pool: Any) -> None:
    """All 10 base participant_roles seeded per ADR-118 V2.38 decision #4."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT d.domain, r.role
            FROM canonical_participant_roles r
            LEFT JOIN canonical_event_domains d ON d.id = r.domain_id
            ORDER BY r.id
            """
        )
        rows = cur.fetchall()
    actual = [(r["domain"], r["role"]) for r in rows]
    for expected_pair in _EXPECTED_PARTICIPANT_ROLES:
        assert expected_pair in actual, (
            f"participant_role pair {expected_pair!r} missing; got {actual!r}"
        )
    assert len(actual) == len(_EXPECTED_PARTICIPANT_ROLES), (
        f"canonical_participant_roles row count drifted; expected {len(_EXPECTED_PARTICIPANT_ROLES)}, "
        f"got {len(actual)}: {actual!r}"
    )


def test_participant_role_fk_resolves_to_correct_domain(db_pool: Any) -> None:
    """Every seeded participant_role row has a non-NULL domain_id (initial seed has no cross-domain rows)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT r.id, r.role, r.domain_id, d.domain
            FROM canonical_participant_roles r
            LEFT JOIN canonical_event_domains d ON d.id = r.domain_id
            """
        )
        rows = cur.fetchall()
    # All initial seed rows must have a resolved domain (per migration docstring:
    # "All seed rows have concrete domain_id (no cross-domain rows in the initial seed)").
    for row in rows:
        assert row["domain"] is not None, (
            f"participant_role id={row['id']} ({row['role']!r}) seeded with NULL "
            f"domain_id -- initial seed should have no cross-domain rows"
        )


# =============================================================================
# Group 3: CONSTRAINT TRIGGER -- polymorphic typed back-ref enforcement
#
# This is the highest-value gap closed by this PR.  Pre-1012, the trigger's
# *existence* was MCP-verified but its *body* was never exercised.  These
# tests fire the trigger with each behavioral case from ADR-118 V2.38 lines
# ~17376-17398.
# =============================================================================


def _entity_kind_id(entity_kind: str) -> int:
    """Resolve entity_kind text -> id from the seeded lookup table."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT id FROM canonical_entity_kinds WHERE entity_kind = %s",
            (entity_kind,),
        )
        row = cur.fetchone()
    assert row is not None, f"entity_kind {entity_kind!r} must be seeded"
    return int(row["id"])


def _real_team_id() -> int:
    """Return a real teams.team_id for the team-kind happy path.

    The trigger only enforces ``entity_kind='team' => ref_team_id NOT NULL``;
    the FK on ``ref_team_id REFERENCES teams(team_id)`` enforces the value
    is a real team id.  Fetch one from the live seed.
    """
    with get_cursor() as cur:
        cur.execute("SELECT team_id FROM teams ORDER BY team_id LIMIT 1")
        row = cur.fetchone()
    assert row is not None, "teams table must have at least one seed row"
    return int(row["team_id"])


def test_constraint_trigger_blocks_team_kind_with_null_ref_team_id(
    db_pool: Any,
) -> None:
    """INSERT entity_kind='team' + ref_team_id=NULL must raise (the trigger fires).

    Behavioral spec from migration line ~282-286:
        IF v_entity_kind = 'team' AND NEW.ref_team_id IS NULL THEN
            RAISE EXCEPTION '...';
        END IF;
    """
    team_kind_id = _entity_kind_id("team")
    suffix = uuid.uuid4().hex[:8]
    entity_key = f"TEST-1012-trg-block-{suffix}"

    # Cleanup any residue from a prior failed run.
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM canonical_entity WHERE entity_key = %s",
            (entity_key,),
        )

    try:
        with pytest.raises(psycopg2.errors.RaiseException):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_entity
                        (entity_kind_id, entity_key, display_name, ref_team_id)
                    VALUES (%s, %s, %s, NULL)
                    """,
                    (team_kind_id, entity_key, "Test Team With NULL Backref"),
                )
    finally:
        # get_cursor's __exit__ calls conn.rollback() on exception and
        # release_connection() returns the connection to the pool. The cleanup
        # `with get_cursor` below pulls a fresh / clean connection from the
        # pool, so the aborted-transaction state from the RaiseException above
        # does NOT leak into the cleanup INSERT. No explicit ROLLBACK needed.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_entity WHERE entity_key = %s",
                (entity_key,),
            )


def test_constraint_trigger_allows_team_kind_with_valid_ref_team_id(
    db_pool: Any,
) -> None:
    """INSERT entity_kind='team' + valid team_id must succeed (happy path)."""
    team_kind_id = _entity_kind_id("team")
    real_team_id = _real_team_id()
    suffix = uuid.uuid4().hex[:8]
    entity_key = f"TEST-1012-trg-ok-{suffix}"

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM canonical_entity WHERE entity_key = %s",
            (entity_key,),
        )

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_entity
                    (entity_kind_id, entity_key, display_name, ref_team_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (team_kind_id, entity_key, "Test Team With Valid Backref", real_team_id),
            )
            inserted_id = cur.fetchone()["id"]
        assert inserted_id is not None, "INSERT must return the new id on success"
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_entity WHERE entity_key = %s",
                (entity_key,),
            )


def test_constraint_trigger_skips_non_team_kind_with_null_ref_team_id(
    db_pool: Any,
) -> None:
    """INSERT entity_kind='fighter' + ref_team_id=NULL must succeed (trigger skip path).

    Per migration line ~282: ``IF v_entity_kind = 'team'``.  The trigger
    ONLY raises when entity_kind resolves to 'team'.  Other entity_kinds
    pass through with NULL ref_team_id.
    """
    fighter_kind_id = _entity_kind_id("fighter")
    suffix = uuid.uuid4().hex[:8]
    entity_key = f"TEST-1012-trg-skip-{suffix}"

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM canonical_entity WHERE entity_key = %s",
            (entity_key,),
        )

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_entity
                    (entity_kind_id, entity_key, display_name, ref_team_id)
                VALUES (%s, %s, %s, NULL)
                RETURNING id
                """,
                (fighter_kind_id, entity_key, "Test Fighter (no team back-ref)"),
            )
            inserted_id = cur.fetchone()["id"]
        assert inserted_id is not None, (
            "fighter-kind row with NULL ref_team_id must succeed (trigger skip path)"
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_entity WHERE entity_key = %s",
                (entity_key,),
            )


def test_constraint_trigger_blocks_update_to_team_kind_with_null_ref_team_id(
    db_pool: Any,
) -> None:
    """UPDATE entity_kind_id -> 'team' on a row with ref_team_id=NULL must raise.

    The trigger fires on ``UPDATE OF entity_kind_id, ref_team_id`` per
    migration line ~296.  Seed a fighter row (NULL ref_team_id allowed),
    then attempt to morph it into a team row -- the trigger must block.
    """
    fighter_kind_id = _entity_kind_id("fighter")
    team_kind_id = _entity_kind_id("team")
    suffix = uuid.uuid4().hex[:8]
    entity_key = f"TEST-1012-trg-update-{suffix}"

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM canonical_entity WHERE entity_key = %s",
            (entity_key,),
        )

    try:
        # Step 1: seed a fighter row (NULL ref_team_id allowed by trigger skip).
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_entity
                    (entity_kind_id, entity_key, display_name, ref_team_id)
                VALUES (%s, %s, %s, NULL)
                """,
                (fighter_kind_id, entity_key, "Test Fighter -> Team morph attempt"),
            )

        # Step 2: morph entity_kind to 'team' -- trigger must fire on UPDATE.
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
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_entity WHERE entity_key = %s",
                (entity_key,),
            )


def test_constraint_trigger_is_deferrable_initially_immediate(db_pool: Any) -> None:
    """The CONSTRAINT TRIGGER is DEFERRABLE INITIALLY IMMEDIATE per migration line ~297."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_triggerdef(oid) AS def
            FROM pg_trigger
            WHERE tgname = 'trg_canonical_entity_team_backref'
              AND NOT tgisinternal
            """
        )
        row = cur.fetchone()
    assert row is not None, "trg_canonical_entity_team_backref must exist"
    trigger_def = row["def"]
    assert "CONSTRAINT TRIGGER" in trigger_def, (
        f"Must be a CONSTRAINT TRIGGER (Pattern 82); got: {trigger_def}"
    )
    assert "DEFERRABLE" in trigger_def, f"Must be DEFERRABLE; got: {trigger_def}"
    assert "INITIALLY IMMEDIATE" in trigger_def, f"Must be INITIALLY IMMEDIATE; got: {trigger_def}"


# =============================================================================
# Group 4: Indexes (4 full + 2 partial WHERE)
# =============================================================================


@pytest.mark.parametrize(
    ("table", "indexname", "must_be_unique", "partial_predicate"),
    _EXPECTED_INDEXES,
)
def test_index_exists_with_expected_shape(
    db_pool: Any,
    table: str,
    indexname: str,
    must_be_unique: bool,
    partial_predicate: str | None,
) -> None:
    """Each FK-column index exists with the migration-prescribed UNIQUE-ness + WHERE clause."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = %s AND indexname = %s",
            (table, indexname),
        )
        row = cur.fetchone()
    assert row is not None, f"{table}.{indexname} missing post-0068"
    indexdef = row["indexdef"]

    if must_be_unique:
        assert "CREATE UNIQUE" in indexdef, f"{indexname} must be UNIQUE; got: {indexdef}"
    else:
        assert "CREATE UNIQUE" not in indexdef, f"{indexname} must NOT be UNIQUE; got: {indexdef}"

    if partial_predicate is not None:
        assert partial_predicate in indexdef, (
            f"{indexname} must have partial WHERE {partial_predicate!r}; got: {indexdef}"
        )
    else:
        assert " WHERE " not in indexdef, f"{indexname} must NOT be partial; got: {indexdef}"


def test_canonical_entity_unique_kind_key(db_pool: Any) -> None:
    """``uq_canonical_entity_kind_key`` enforces UNIQUE (entity_kind_id, entity_key)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_entity'::regclass
              AND conname = 'uq_canonical_entity_kind_key'
            """
        )
        row = cur.fetchone()
    assert row is not None, "uq_canonical_entity_kind_key must exist"
    assert "UNIQUE (entity_kind_id, entity_key)" in row["def"], (
        f"uq_canonical_entity_kind_key must enforce composite UNIQUE; got: {row['def']}"
    )


def test_canonical_event_participants_composite_unique(db_pool: Any) -> None:
    """``uq_canonical_event_participants`` enforces UNIQUE (canonical_event_id, role_id, sequence_number)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_event_participants'::regclass
              AND conname = 'uq_canonical_event_participants'
            """
        )
        row = cur.fetchone()
    assert row is not None, "uq_canonical_event_participants must exist"
    assert "UNIQUE (canonical_event_id, role_id, sequence_number)" in row["def"], (
        f"uq_canonical_event_participants must enforce 3-column composite UNIQUE; got: {row['def']}"
    )


# =============================================================================
# Group 5: ON DELETE clauses on canonical_event_participants FKs (#1044 item 3)
#
# Mirrors the ON DELETE RESTRICT assertion in test_0069 against
# ``canonical_markets_canonical_event_id_fkey``.  The 3 FKs differ:
#   - canonical_event_id -> canonical_events(id)        ON DELETE CASCADE
#     (participants are denormalization; deleting the parent event must
#     cascade-clean its participant rows -- no orphans)
#   - entity_id          -> canonical_entity(id)        ON DELETE RESTRICT
#     (deleting an entity referenced by a participant row is a data-loss
#     hazard; force the caller to detach explicitly)
#   - role_id            -> canonical_participant_roles ON DELETE RESTRICT
#     (same rationale; lookup-table rows must not be deleted while in use)
# =============================================================================


@pytest.mark.parametrize(
    ("constraint_name", "expected_clause"),
    [
        (
            "canonical_event_participants_canonical_event_id_fkey",
            "ON DELETE CASCADE",
        ),
        (
            "canonical_event_participants_entity_id_fkey",
            "ON DELETE RESTRICT",
        ),
        (
            "canonical_event_participants_role_id_fkey",
            "ON DELETE RESTRICT",
        ),
    ],
)
def test_canonical_event_participants_fk_on_delete_clause(
    db_pool: Any,
    constraint_name: str,
    expected_clause: str,
) -> None:
    """Pin the ON DELETE clause on each canonical_event_participants FK."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_event_participants'::regclass
              AND conname = %s
            """,
            (constraint_name,),
        )
        row = cur.fetchone()
    assert row is not None, f"{constraint_name} must exist on canonical_event_participants"
    fk_def = row["def"]
    assert expected_clause in fk_def, (
        f"{constraint_name} must include {expected_clause!r}; got: {fk_def}"
    )
