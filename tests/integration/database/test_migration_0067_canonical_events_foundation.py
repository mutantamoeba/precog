"""Integration tests for migration 0067 -- Cohort 1A canonical events foundation.

Verifies the POST-MIGRATION state of the three canonical-event tables introduced
by migration 0067 -- ``canonical_event_domains``, ``canonical_event_types``, and
``canonical_events`` -- plus the lookup-table seed rows (7 domains + 13 per-domain
event types) and the FK-column indexes (5 total, two of them partial).

Test groups:
    - TestTableShapes: each of the three tables exists with the expected
      columns / types / nullability / defaults (parametrized per ``_TABLE_SPEC``).
    - TestSeedRows: ``canonical_event_domains`` has the 7 base domains and
      ``canonical_event_types`` has the 13 per-domain event types per
      ADR-118 V2.38 decisions #2 + #3, with FK domain_id resolutions verified.
    - TestIdempotentSeed: the ``ON CONFLICT DO NOTHING`` seed paths in the
      migration are idempotent -- re-running the seed inserts is a no-op.
    - TestIndexes: 5 indexes per migration (3 full + 2 partial WHERE).

Issue: #1012
Epic: #972 (Canonical Layer Foundation -- Phase B.5)

Markers:
    @pytest.mark.integration: real DB required.
"""

from __future__ import annotations

from typing import Any

import pytest

from precog.database.connection import get_cursor

pytestmark = [pytest.mark.integration]


# =============================================================================
# Per-table column spec (mirrors migration 0067 DDL verbatim).
#
# Each tuple: (column_name, data_type, is_nullable, default_substring_or_None).
# ``default_substring_or_None`` is matched case-insensitively as a substring
# on ``column_default`` so SERIAL ``nextval('..._id_seq')`` and ``now()`` defaults
# are robust against PG textual reformatting.
# =============================================================================

_DOMAINS_COLS: list[tuple[str, str, str, str | None]] = [
    ("id", "integer", "NO", "nextval"),
    ("domain", "text", "NO", None),
    ("description", "text", "YES", None),
    ("created_at", "timestamp with time zone", "NO", "now()"),
]

_EVENT_TYPES_COLS: list[tuple[str, str, str, str | None]] = [
    ("id", "integer", "NO", "nextval"),
    ("domain_id", "integer", "NO", None),
    ("event_type", "text", "NO", None),
    ("description", "text", "YES", None),
    ("created_at", "timestamp with time zone", "NO", "now()"),
]

_EVENTS_COLS: list[tuple[str, str, str, str | None]] = [
    ("id", "bigint", "NO", "nextval"),
    ("domain_id", "integer", "NO", None),
    ("event_type_id", "integer", "NO", None),
    ("entities_sorted", "ARRAY", "NO", None),
    ("resolution_window", "tstzrange", "NO", None),
    ("resolution_rule_fp", "bytea", "YES", None),
    ("natural_key_hash", "bytea", "NO", None),
    ("title", "character varying", "NO", None),
    ("description", "text", "YES", None),
    ("game_id", "integer", "YES", None),
    ("series_id", "integer", "YES", None),
    ("lifecycle_phase", "character varying", "NO", "proposed"),
    ("metadata", "jsonb", "YES", None),
    ("created_at", "timestamp with time zone", "NO", "now()"),
    ("updated_at", "timestamp with time zone", "NO", "now()"),
    ("retired_at", "timestamp with time zone", "YES", None),
]

# Combined parametrization spec: (table, [column_specs])
_TABLE_SPEC: list[tuple[str, list[tuple[str, str, str, str | None]]]] = [
    ("canonical_event_domains", _DOMAINS_COLS),
    ("canonical_event_types", _EVENT_TYPES_COLS),
    ("canonical_events", _EVENTS_COLS),
]


# Expected seed rows (verbatim from migration ``_DOMAIN_SEED`` /
# ``_EVENT_TYPE_SEED``).  Pattern 73 SSOT: any drift from these forces
# the test to be updated alongside the migration -- intentional gate.
_EXPECTED_DOMAINS: list[str] = [
    "sports",
    "politics",
    "weather",
    "econ",
    "news",
    "entertainment",
    "fighting",
]

_EXPECTED_EVENT_TYPES: list[tuple[str, str]] = [
    ("sports", "game"),
    ("sports", "match"),
    ("politics", "election"),
    ("politics", "debate"),
    ("politics", "referendum"),
    ("weather", "storm_track"),
    ("weather", "temperature_range"),
    ("econ", "earnings_release"),
    ("econ", "rate_decision"),
    ("news", "pandemic_case"),
    ("news", "conflict_outcome"),
    ("entertainment", "award_winner"),
    ("entertainment", "box_office_result"),
]


# Expected indexes per migration upgrade() body (PK / UNIQUE indexes excluded
# -- those are covered by the constraint tests below).  Each tuple:
# (table, indexname, must_be_unique, partial_predicate_or_None).
_EXPECTED_INDEXES: list[tuple[str, str, bool, str | None]] = [
    ("canonical_event_types", "idx_canonical_event_types_domain_id", False, None),
    ("canonical_events", "idx_canonical_events_domain_id", False, None),
    ("canonical_events", "idx_canonical_events_event_type_id", False, None),
    (
        "canonical_events",
        "idx_canonical_events_game_id",
        False,
        "game_id IS NOT NULL",
    ),
    (
        "canonical_events",
        "idx_canonical_events_series_id",
        False,
        "series_id IS NOT NULL",
    ),
]


# =============================================================================
# Group 1: Table shapes (columns / types / nullability / defaults)
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


def test_canonical_events_lifecycle_phase_default_is_proposed(db_pool: Any) -> None:
    """``canonical_events.lifecycle_phase`` defaults to ``'proposed'`` per ADR-118 V2.38 state machine."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT column_default
            FROM information_schema.columns
            WHERE table_name = 'canonical_events'
              AND column_name = 'lifecycle_phase'
            """
        )
        row = cur.fetchone()
    assert row is not None, "canonical_events.lifecycle_phase must exist"
    default = row["column_default"] or ""
    assert "proposed" in default, f"lifecycle_phase must default to 'proposed'; got {default!r}"


# =============================================================================
# Group 2: Seed rows (7 domains + 13 event_types) with FK resolutions
# =============================================================================


def test_canonical_event_domains_has_all_seed_rows(db_pool: Any) -> None:
    """All 7 base domains seeded per ADR-118 V2.38 decision #2."""
    with get_cursor() as cur:
        cur.execute("SELECT domain FROM canonical_event_domains ORDER BY id")
        rows = cur.fetchall()
    actual = [r["domain"] for r in rows]
    for expected_domain in _EXPECTED_DOMAINS:
        assert expected_domain in actual, (
            f"domain {expected_domain!r} missing from canonical_event_domains; got {actual!r}"
        )


def test_canonical_event_types_has_all_seed_rows(db_pool: Any) -> None:
    """All 13 per-domain event types seeded per ADR-118 V2.38 decision #3.

    Notably absent: ``fighting`` event types -- the ``fighting`` domain
    exists for ``canonical_participant_roles`` FK in 0068, but no
    fighting event types are seeded (INSERT-not-ALTER discipline; first
    fighting event type lands with the first fighting market).
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT d.domain, t.event_type
            FROM canonical_event_types t
            JOIN canonical_event_domains d ON d.id = t.domain_id
            ORDER BY t.id
            """
        )
        rows = cur.fetchall()
    actual = [(r["domain"], r["event_type"]) for r in rows]
    for expected_pair in _EXPECTED_EVENT_TYPES:
        assert expected_pair in actual, (
            f"event_type pair {expected_pair!r} missing from canonical_event_types; got {actual!r}"
        )

    # Carry-forward verification: zero fighting event_types seeded (per migration docstring).
    fighting_types = [pair for pair in actual if pair[0] == "fighting"]
    assert fighting_types == [], (
        f"No fighting event_types should be seeded by migration 0067; got {fighting_types!r}"
    )


def test_canonical_event_types_fk_resolves_to_correct_domain(db_pool: Any) -> None:
    """Every event_type row's domain_id resolves to a non-NULL canonical_event_domains row."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT t.id, t.event_type, t.domain_id, d.domain
            FROM canonical_event_types t
            LEFT JOIN canonical_event_domains d ON d.id = t.domain_id
            """
        )
        rows = cur.fetchall()
    for row in rows:
        assert row["domain"] is not None, (
            f"event_type id={row['id']} ({row['event_type']!r}) has dangling "
            f"domain_id={row['domain_id']}"
        )


# =============================================================================
# Group 3: Idempotent seed (ON CONFLICT DO NOTHING)
# =============================================================================


def test_domain_seed_insert_is_idempotent(db_pool: Any) -> None:
    """Re-inserting a seed domain via ON CONFLICT DO NOTHING is a no-op (no duplicates)."""
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM canonical_event_domains")
        pre_count = int(cur.fetchone()["n"])

    # Re-execute the seed insert for one of the existing domains.
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO canonical_event_domains (domain, description) "
            "VALUES (%s, %s) ON CONFLICT (domain) DO NOTHING",
            ("sports", "Sports events (re-insert smoke test)"),
        )

    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM canonical_event_domains")
        post_count = int(cur.fetchone()["n"])

    assert post_count == pre_count, (
        f"ON CONFLICT DO NOTHING re-insert must be a no-op; pre={pre_count}, post={post_count}"
    )


def test_event_type_seed_insert_is_idempotent(db_pool: Any) -> None:
    """Re-inserting a seed event_type via ON CONFLICT DO NOTHING is a no-op."""
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM canonical_event_types")
        pre_count = int(cur.fetchone()["n"])

    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO canonical_event_types (domain_id, event_type, description) "
            "VALUES ("
            "    (SELECT id FROM canonical_event_domains WHERE domain = %s),"
            "    %s, %s"
            ") ON CONFLICT (domain_id, event_type) DO NOTHING",
            ("sports", "game", "re-insert smoke test"),
        )

    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM canonical_event_types")
        post_count = int(cur.fetchone()["n"])

    assert post_count == pre_count, (
        f"ON CONFLICT DO NOTHING re-insert on event_types must be a no-op; "
        f"pre={pre_count}, post={post_count}"
    )


# =============================================================================
# Group 4: Indexes (3 full + 2 partial WHERE)
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
    assert row is not None, f"{table}.{indexname} missing post-0067"
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


def test_canonical_events_natural_key_hash_unique(db_pool: Any) -> None:
    """``uq_canonical_events_nk`` enforces UNIQUE (natural_key_hash)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_events'::regclass
              AND conname = 'uq_canonical_events_nk'
            """
        )
        row = cur.fetchone()
    assert row is not None, "uq_canonical_events_nk must exist"
    assert "UNIQUE (natural_key_hash)" in row["def"], (
        f"uq_canonical_events_nk must enforce UNIQUE (natural_key_hash); got: {row['def']}"
    )
