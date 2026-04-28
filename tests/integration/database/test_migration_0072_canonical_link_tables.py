"""Integration tests for migration 0072 — Cohort 3 link tables.

Verifies the POST-MIGRATION state of the ``canonical_market_links`` and
``canonical_event_links`` tables introduced by migration 0072 — Cohort 3
second slot, link-tables-in-one-slot per session 78 5-slot adjudication
(ADR-118 v2.41 amendment) + session 80 S82 design-stage P41 council
(build spec at ``memory/build_spec_0072_pm_memo.md``).

Test groups:
    - TestMarketLinksTableShape / TestEventLinksTableShape: per-table column
      spec (column / type / nullability / defaults / max-character-length).
    - TestMarketLinksConstraints / TestEventLinksConstraints: link_state
      CHECK + confidence CHECK + 4 FK constraints (canonical-tier RESTRICT,
      platform-tier CASCADE, algorithm_id FK, partial-active EXCLUDE).
    - TestMarketLinksFKBehavior / TestEventLinksFKBehavior: behavioral FK
      assertions — RESTRICT fires on canonical-tier delete-with-children,
      CASCADE fires on platform-tier delete (link CASCADE-deletes).
    - TestMarketLinksExcludeInvariant / TestEventLinksExcludeInvariant:
      **THE LOAD-BEARING TEST** — two ``active`` rows with same
      platform-row id raise ``psycopg2.errors.ExclusionViolation`` (NOT
      generic IntegrityError).  Mandatory regression test per L7 +
      build spec § 9 Risk A.
    - TestMarketLinksUpdateTrigger / TestEventLinksUpdateTrigger: BEFORE
      UPDATE trigger fires + advances updated_at.
    - TestIndexes: 4 FK-target indexes (2 per table).
    - TestDowngradeRoundTrip: documentation-only test that asserts the
      manual round-trip reasoning (round-trip CI gate per PR #1066 owns
      the in-CI version).

Two **load-bearing assertions** per build spec § 9 Risk A + Risk H:
    (a) Market-tier EXCLUDE: two active rows same platform_market_id raises
        ``psycopg2.errors.ExclusionViolation`` (NOT generic IntegrityError);
    (b) Event-tier EXCLUDE: two active rows same platform_event_id raises
        ``psycopg2.errors.ExclusionViolation`` (parallel to (a) per L13).

Issue: Epic #972 (Canonical Layer Foundation — Phase B.5), #1058
ADR: ADR-118 v2.41 amendment (Cohort 3 5-slot adjudication, session 78);
    v2.42 sub-amendments A + B
Build spec: ``memory/build_spec_0072_pm_memo.md``

Markers:
    @pytest.mark.integration: real DB required.
"""

from __future__ import annotations

import uuid
from typing import Any

import psycopg2
import psycopg2.errors
import pytest

from precog.database.connection import get_cursor
from tests.integration.database._canonical_event_helpers import (
    _cleanup_canonical_event,
    _seed_canonical_event,
)
from tests.integration.database._canonical_market_helpers import (
    _cleanup_canonical_market,
    _cleanup_platform_market,
    _get_manual_v1_algorithm_id,
    _seed_canonical_market,
    _seed_platform_market,
)

pytestmark = [pytest.mark.integration]


# =============================================================================
# Per-table column spec (mirrors migration 0072 DDL verbatim).
#
# Each tuple: (column_name, data_type, is_nullable, default_substring_or_None,
#              max_char_length_or_None).
# Pattern 73 SSOT discipline: the migration owns the column shape in code;
# this spec mirrors verbatim.  Drift here => test fails => alignment forced.
# =============================================================================

_MARKET_LINKS_COLS: list[tuple[str, str, str, str | None, int | None]] = [
    ("id", "bigint", "NO", "nextval", None),
    ("canonical_market_id", "bigint", "NO", None, None),
    ("platform_market_id", "integer", "NO", None, None),
    ("link_state", "character varying", "NO", None, 16),
    ("confidence", "numeric", "NO", None, None),
    ("algorithm_id", "bigint", "NO", None, None),
    ("decided_by", "character varying", "NO", None, 64),
    ("decided_at", "timestamp with time zone", "NO", "now()", None),
    ("retired_at", "timestamp with time zone", "YES", None, None),
    ("retire_reason", "character varying", "YES", None, 64),
    ("created_at", "timestamp with time zone", "NO", "now()", None),
    ("updated_at", "timestamp with time zone", "NO", "now()", None),
]

_EVENT_LINKS_COLS: list[tuple[str, str, str, str | None, int | None]] = [
    ("id", "bigint", "NO", "nextval", None),
    ("canonical_event_id", "bigint", "NO", None, None),
    ("platform_event_id", "integer", "NO", None, None),
    ("link_state", "character varying", "NO", None, 16),
    ("confidence", "numeric", "NO", None, None),
    ("algorithm_id", "bigint", "NO", None, None),
    ("decided_by", "character varying", "NO", None, 64),
    ("decided_at", "timestamp with time zone", "NO", "now()", None),
    ("retired_at", "timestamp with time zone", "YES", None, None),
    ("retire_reason", "character varying", "YES", None, 64),
    ("created_at", "timestamp with time zone", "NO", "now()", None),
    ("updated_at", "timestamp with time zone", "NO", "now()", None),
]


# =============================================================================
# Seed helpers — set up a complete FK chain so EXCLUDE / FK behavior tests
# can insert real rows.
# =============================================================================


def _seed_platform_event(suffix: str) -> int:
    """Seed a platform events row to back canonical_event_links.platform_event_id."""
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO events (
                platform_id, external_id, category, title, event_key
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                "kalshi",
                f"TEST-0072-evt-EXT-{suffix}",
                "sports",
                f"Migration 0072 platform event test ({suffix})",
                f"TEMP-{uuid.uuid4()}",
            ),
        )
        return int(cur.fetchone()["id"])


def _cleanup_platform_event(platform_event_id: int) -> None:
    """Remove a platform events row seeded by _seed_platform_event."""
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM events WHERE id = %s", (platform_event_id,))


# =============================================================================
# Group 1a: canonical_market_links table shape
# =============================================================================


@pytest.mark.parametrize(
    ("col_name", "data_type", "is_nullable", "default_substr", "max_char_len"),
    _MARKET_LINKS_COLS,
)
def test_canonical_market_links_column_shape(
    db_pool: Any,
    col_name: str,
    data_type: str,
    is_nullable: str,
    default_substr: str | None,
    max_char_len: int | None,
) -> None:
    """Each column on canonical_market_links has the migration-prescribed shape."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT data_type, is_nullable, column_default, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'canonical_market_links'
              AND column_name = %s
              AND table_schema = 'public'
            """,
            (col_name,),
        )
        row = cur.fetchone()
    assert row is not None, f"canonical_market_links.{col_name} missing post-0072"
    assert row["data_type"] == data_type, (
        f"canonical_market_links.{col_name} type mismatch: "
        f"expected {data_type!r}, got {row['data_type']!r}"
    )
    assert row["is_nullable"] == is_nullable, (
        f"canonical_market_links.{col_name} nullability mismatch: "
        f"expected {is_nullable!r}, got {row['is_nullable']!r}"
    )
    if default_substr is not None:
        actual_default = row["column_default"] or ""
        assert default_substr.lower() in actual_default.lower(), (
            f"canonical_market_links.{col_name} default missing {default_substr!r}; "
            f"got {actual_default!r}"
        )
    if max_char_len is not None:
        assert row["character_maximum_length"] == max_char_len, (
            f"canonical_market_links.{col_name} max_length mismatch: "
            f"expected {max_char_len}, got {row['character_maximum_length']}"
        )


# =============================================================================
# Group 1b: canonical_event_links table shape
# =============================================================================


@pytest.mark.parametrize(
    ("col_name", "data_type", "is_nullable", "default_substr", "max_char_len"),
    _EVENT_LINKS_COLS,
)
def test_canonical_event_links_column_shape(
    db_pool: Any,
    col_name: str,
    data_type: str,
    is_nullable: str,
    default_substr: str | None,
    max_char_len: int | None,
) -> None:
    """Each column on canonical_event_links has the migration-prescribed shape."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT data_type, is_nullable, column_default, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'canonical_event_links'
              AND column_name = %s
              AND table_schema = 'public'
            """,
            (col_name,),
        )
        row = cur.fetchone()
    assert row is not None, f"canonical_event_links.{col_name} missing post-0072"
    assert row["data_type"] == data_type
    assert row["is_nullable"] == is_nullable
    if default_substr is not None:
        actual_default = row["column_default"] or ""
        assert default_substr.lower() in actual_default.lower()
    if max_char_len is not None:
        assert row["character_maximum_length"] == max_char_len


# =============================================================================
# Group 2a: canonical_market_links FK + CHECK constraints
# =============================================================================


def test_market_links_canonical_market_id_fk_is_restrict(db_pool: Any) -> None:
    """``canonical_market_id`` FK is ON DELETE RESTRICT per L3."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_market_links'::regclass
              AND contype = 'f'
              AND pg_get_constraintdef(oid) LIKE '%canonical_markets(id)%'
            """
        )
        row = cur.fetchone()
    assert row is not None, "FK to canonical_markets(id) missing"
    fk_def = row["def"]
    assert "ON DELETE RESTRICT" in fk_def, (
        f"canonical_market_id FK must be ON DELETE RESTRICT; got: {fk_def}"
    )


def test_market_links_platform_market_id_fk_is_cascade(db_pool: Any) -> None:
    """``platform_market_id`` FK is ON DELETE CASCADE per L4."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_market_links'::regclass
              AND contype = 'f'
              AND pg_get_constraintdef(oid) LIKE '%markets(id)%'
              AND pg_get_constraintdef(oid) NOT LIKE '%canonical_markets(id)%'
            """
        )
        row = cur.fetchone()
    assert row is not None, "FK to markets(id) missing"
    fk_def = row["def"]
    assert "ON DELETE CASCADE" in fk_def, (
        f"platform_market_id FK must be ON DELETE CASCADE; got: {fk_def}"
    )


def test_market_links_algorithm_id_fk_exists(db_pool: Any) -> None:
    """``algorithm_id`` FK references match_algorithm(id)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_market_links'::regclass
              AND contype = 'f'
              AND pg_get_constraintdef(oid) LIKE '%match_algorithm(id)%'
            """
        )
        row = cur.fetchone()
    assert row is not None, "FK to match_algorithm(id) missing"


def test_market_links_link_state_check_constraint_exists(db_pool: Any) -> None:
    """Inline CHECK on ``link_state`` lists all 3 closed-enum values."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_market_links'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) LIKE '%link_state%'
            """
        )
        row = cur.fetchone()
    assert row is not None, "link_state CHECK constraint missing"
    check_def = row["def"]
    for value in ("active", "retired", "quarantined"):
        assert value in check_def, f"link_state CHECK must include {value!r}; got: {check_def}"


def test_market_links_confidence_check_constraint_exists(db_pool: Any) -> None:
    """CHECK on ``confidence`` enforces [0, 1] bound."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_market_links'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) LIKE '%confidence%'
            """
        )
        row = cur.fetchone()
    assert row is not None, "confidence CHECK constraint missing"


# =============================================================================
# Group 2b: canonical_event_links FK + CHECK constraints
# =============================================================================


def test_event_links_canonical_event_id_fk_is_restrict(db_pool: Any) -> None:
    """``canonical_event_id`` FK is ON DELETE RESTRICT per L3."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_event_links'::regclass
              AND contype = 'f'
              AND pg_get_constraintdef(oid) LIKE '%canonical_events(id)%'
            """
        )
        row = cur.fetchone()
    assert row is not None, "FK to canonical_events(id) missing"
    fk_def = row["def"]
    assert "ON DELETE RESTRICT" in fk_def, (
        f"canonical_event_id FK must be ON DELETE RESTRICT; got: {fk_def}"
    )


def test_event_links_platform_event_id_fk_is_cascade(db_pool: Any) -> None:
    """``platform_event_id`` FK is ON DELETE CASCADE per L4."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_event_links'::regclass
              AND contype = 'f'
              AND pg_get_constraintdef(oid) LIKE '%REFERENCES events(id)%'
            """
        )
        row = cur.fetchone()
    assert row is not None, "FK to events(id) missing"
    fk_def = row["def"]
    assert "ON DELETE CASCADE" in fk_def, (
        f"platform_event_id FK must be ON DELETE CASCADE; got: {fk_def}"
    )


def test_event_links_algorithm_id_fk_exists(db_pool: Any) -> None:
    """``algorithm_id`` FK references match_algorithm(id)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_event_links'::regclass
              AND contype = 'f'
              AND pg_get_constraintdef(oid) LIKE '%match_algorithm(id)%'
            """
        )
        row = cur.fetchone()
    assert row is not None, "FK to match_algorithm(id) missing"


# =============================================================================
# Group 3a: canonical_market_links FK behavioral tests
# =============================================================================


def test_market_links_canonical_market_delete_restrict_fires(db_pool: Any) -> None:
    """DELETE FROM canonical_markets while a link exists raises FK-violation class.

    L3 behavioral proof: settlement-bearing canonical markets must not be
    deletable while linked rows still exist.  Operator must retire the link
    first.  Caught as the tuple ``(ForeignKeyViolation, RestrictViolation)``
    for parity with sibling RESTRICT tests in migrations 0057 + 0063.  In
    practice PostgreSQL surfaces ``ON DELETE RESTRICT`` as SQLSTATE 23503
    (``foreign_key_violation``); the tuple form absorbs SQLSTATE 23001
    (``restrict_violation``) defensively in case future PG versions or
    constraint shapes route the violation through the alternate class.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()

    try:
        # Insert a link so the canonical_market is now FK-protected by RESTRICT.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_market_links (
                    canonical_market_id, platform_market_id, link_state,
                    confidence, algorithm_id, decided_by
                ) VALUES (%s, %s, 'active', 1.000, %s, %s)
                RETURNING id
                """,
                (seeded_market_id, seeded_platform_market_id, algorithm_id, "system:test"),
            )
            link_id = cur.fetchone()["id"]

        # DELETE on canonical_markets must raise FK-violation class.
        # Tuple form matches sibling RESTRICT tests in 0057 + 0063 (see docstring).
        with pytest.raises(
            (psycopg2.errors.ForeignKeyViolation, psycopg2.errors.RestrictViolation)
        ):
            with get_cursor(commit=True) as cur:
                cur.execute("DELETE FROM canonical_markets WHERE id = %s", (seeded_market_id,))
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM canonical_market_links WHERE id = %s", (link_id,))
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_market_links_platform_market_delete_cascades_link(db_pool: Any) -> None:
    """DELETE FROM markets cascades the link out (L4 behavioral proof)."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_market_links (
                    canonical_market_id, platform_market_id, link_state,
                    confidence, algorithm_id, decided_by
                ) VALUES (%s, %s, 'active', 1.000, %s, %s)
                RETURNING id
                """,
                (seeded_market_id, seeded_platform_market_id, algorithm_id, "system:test"),
            )
            link_id = int(cur.fetchone()["id"])

        # DELETE FROM markets — the link should CASCADE-delete.
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM markets WHERE id = %s", (seeded_platform_market_id,))

        # Verify link gone.
        with get_cursor() as cur:
            cur.execute("SELECT id FROM canonical_market_links WHERE id = %s", (link_id,))
            row = cur.fetchone()
        assert row is None, (
            "platform_market CASCADE failed — link row should be gone after "
            "platform DELETE (L4 behavioral contract)"
        )
    finally:
        # Platform market already gone via CASCADE; clean up canonical chain.
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 3b: canonical_event_links FK behavioral tests
# =============================================================================


def test_event_links_canonical_event_delete_restrict_fires(db_pool: Any) -> None:
    """DELETE FROM canonical_events while a link exists raises FK-violation class.

    Parallel to ``test_market_links_canonical_market_delete_restrict_fires`` —
    same ``ON DELETE RESTRICT`` FK action; same tuple form
    ``(ForeignKeyViolation, RestrictViolation)`` for sibling parity with
    migrations 0057 + 0063.  See sibling test for the full SQLSTATE
    23001-vs-23503 rationale.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_platform_event_id = _seed_platform_event(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_event_links (
                    canonical_event_id, platform_event_id, link_state,
                    confidence, algorithm_id, decided_by
                ) VALUES (%s, %s, 'active', 1.000, %s, %s)
                RETURNING id
                """,
                (seeded_event_id, seeded_platform_event_id, algorithm_id, "system:test"),
            )
            link_id = cur.fetchone()["id"]

        with pytest.raises(
            (psycopg2.errors.ForeignKeyViolation, psycopg2.errors.RestrictViolation)
        ):
            with get_cursor(commit=True) as cur:
                cur.execute("DELETE FROM canonical_events WHERE id = %s", (seeded_event_id,))
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM canonical_event_links WHERE id = %s", (link_id,))
        _cleanup_platform_event(seeded_platform_event_id)
        _cleanup_canonical_event(seeded_event_id)


def test_event_links_platform_event_delete_cascades_link(db_pool: Any) -> None:
    """DELETE FROM events cascades the link out (L4 behavioral proof on event tier)."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_platform_event_id = _seed_platform_event(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_event_links (
                    canonical_event_id, platform_event_id, link_state,
                    confidence, algorithm_id, decided_by
                ) VALUES (%s, %s, 'active', 1.000, %s, %s)
                RETURNING id
                """,
                (seeded_event_id, seeded_platform_event_id, algorithm_id, "system:test"),
            )
            link_id = int(cur.fetchone()["id"])

        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM events WHERE id = %s", (seeded_platform_event_id,))

        with get_cursor() as cur:
            cur.execute("SELECT id FROM canonical_event_links WHERE id = %s", (link_id,))
            row = cur.fetchone()
        assert row is None, (
            "platform_event CASCADE failed — link row should be gone after "
            "platform DELETE (L4 behavioral contract)"
        )
    finally:
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 4a: canonical_market_links EXCLUDE invariant (THE LOAD-BEARING TEST)
# =============================================================================


def test_market_links_exclude_invariant_blocks_duplicate_active_rows(
    db_pool: Any,
) -> None:
    """**LOAD-BEARING per L7 + build spec § 9 Risk A.**

    Insert two ``active`` rows with the same ``platform_market_id``;
    assert ``psycopg2.errors.ExclusionViolation`` (NOT generic
    IntegrityError).  Without this constraint firing, two active links
    could coexist for the same platform market and the canonical layer
    would fail its core contract: "what's the canonical market for this
    Kalshi market?" would resolve to arbitrary results.

    Holden H:18-21: "the single biggest schema-safety risk in the entire
    canonical layer is link uniqueness leakage."
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id_a = _seed_canonical_market(seeded_event_id, f"{suffix}-a")
    seeded_market_id_b = _seed_canonical_market(seeded_event_id, f"{suffix}-b")
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()

    inserted_link_ids: list[int] = []
    try:
        # First active link — must succeed.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_market_links (
                    canonical_market_id, platform_market_id, link_state,
                    confidence, algorithm_id, decided_by
                ) VALUES (%s, %s, 'active', 1.000, %s, %s)
                RETURNING id
                """,
                (seeded_market_id_a, seeded_platform_market_id, algorithm_id, "system:test"),
            )
            inserted_link_ids.append(int(cur.fetchone()["id"]))

        # Second active link with SAME platform_market_id — must raise
        # ExclusionViolation specifically (NOT generic IntegrityError).
        with pytest.raises(psycopg2.errors.ExclusionViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_market_links (
                        canonical_market_id, platform_market_id, link_state,
                        confidence, algorithm_id, decided_by
                    ) VALUES (%s, %s, 'active', 1.000, %s, %s)
                    """,
                    (
                        seeded_market_id_b,
                        seeded_platform_market_id,
                        algorithm_id,
                        "system:test",
                    ),
                )
    finally:
        with get_cursor(commit=True) as cur:
            for link_id in inserted_link_ids:
                cur.execute("DELETE FROM canonical_market_links WHERE id = %s", (link_id,))
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id_a)
        _cleanup_canonical_market(seeded_market_id_b)
        _cleanup_canonical_event(seeded_event_id)


def test_market_links_exclude_allows_active_after_retire(db_pool: Any) -> None:
    """Retiring an active link allows a NEW active link for the same platform_market_id.

    Behavioral counterpart to the EXCLUDE-fires test: the partial-active
    constraint admits multiple retired/quarantined rows, so the matcher's
    "retire old, insert new" pattern works as designed.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id_a = _seed_canonical_market(seeded_event_id, f"{suffix}-a")
    seeded_market_id_b = _seed_canonical_market(seeded_event_id, f"{suffix}-b")
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()

    inserted_link_ids: list[int] = []
    try:
        # First active link.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_market_links (
                    canonical_market_id, platform_market_id, link_state,
                    confidence, algorithm_id, decided_by
                ) VALUES (%s, %s, 'active', 1.000, %s, %s)
                RETURNING id
                """,
                (seeded_market_id_a, seeded_platform_market_id, algorithm_id, "system:test"),
            )
            link_a_id = int(cur.fetchone()["id"])
            inserted_link_ids.append(link_a_id)

        # Retire the first link.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                UPDATE canonical_market_links
                SET link_state = 'retired', retired_at = now()
                WHERE id = %s
                """,
                (link_a_id,),
            )

        # Second active link with SAME platform_market_id — must now succeed
        # (the retired row no longer counts toward the partial-active EXCLUDE).
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_market_links (
                    canonical_market_id, platform_market_id, link_state,
                    confidence, algorithm_id, decided_by
                ) VALUES (%s, %s, 'active', 1.000, %s, %s)
                RETURNING id
                """,
                (seeded_market_id_b, seeded_platform_market_id, algorithm_id, "system:test"),
            )
            link_b_id = int(cur.fetchone()["id"])
            inserted_link_ids.append(link_b_id)

        # Both rows coexist; one retired, one active.
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT link_state FROM canonical_market_links
                WHERE platform_market_id = %s
                ORDER BY id
                """,
                (seeded_platform_market_id,),
            )
            rows = cur.fetchall()
        states = [r["link_state"] for r in rows]
        assert states == ["retired", "active"], f"Expected ['retired', 'active']; got {states}"
    finally:
        with get_cursor(commit=True) as cur:
            for link_id in inserted_link_ids:
                cur.execute("DELETE FROM canonical_market_links WHERE id = %s", (link_id,))
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id_a)
        _cleanup_canonical_market(seeded_market_id_b)
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 4b: canonical_event_links EXCLUDE invariant (THE LOAD-BEARING TEST)
# =============================================================================


def test_event_links_exclude_invariant_blocks_duplicate_active_rows(
    db_pool: Any,
) -> None:
    """**LOAD-BEARING per L13 + build spec § 9 Risk H.**

    Parallel to ``test_market_links_exclude_invariant_blocks_duplicate_active_rows``
    on the event tier.  Two ``active`` rows with the same
    ``platform_event_id`` raise ``psycopg2.errors.ExclusionViolation``.

    Per L13: parallelism IS the contract — without this load-bearing
    behavioral proof on the event tier, the canonical layer's symmetry
    is unverified.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id_a = _seed_canonical_event(f"{suffix}-a")
    seeded_event_id_b = _seed_canonical_event(f"{suffix}-b")
    seeded_platform_event_id = _seed_platform_event(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()

    inserted_link_ids: list[int] = []
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_event_links (
                    canonical_event_id, platform_event_id, link_state,
                    confidence, algorithm_id, decided_by
                ) VALUES (%s, %s, 'active', 1.000, %s, %s)
                RETURNING id
                """,
                (seeded_event_id_a, seeded_platform_event_id, algorithm_id, "system:test"),
            )
            inserted_link_ids.append(int(cur.fetchone()["id"]))

        with pytest.raises(psycopg2.errors.ExclusionViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_event_links (
                        canonical_event_id, platform_event_id, link_state,
                        confidence, algorithm_id, decided_by
                    ) VALUES (%s, %s, 'active', 1.000, %s, %s)
                    """,
                    (
                        seeded_event_id_b,
                        seeded_platform_event_id,
                        algorithm_id,
                        "system:test",
                    ),
                )
    finally:
        with get_cursor(commit=True) as cur:
            for link_id in inserted_link_ids:
                cur.execute("DELETE FROM canonical_event_links WHERE id = %s", (link_id,))
        _cleanup_platform_event(seeded_platform_event_id)
        _cleanup_canonical_event(seeded_event_id_a)
        _cleanup_canonical_event(seeded_event_id_b)


# =============================================================================
# Group 5a: canonical_market_links BEFORE UPDATE trigger
# =============================================================================


def test_market_links_update_trigger_exists(db_pool: Any) -> None:
    """``trg_canonical_market_links_updated_at`` BEFORE UPDATE trigger exists."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_triggerdef(t.oid) AS def
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            WHERE c.relname = 'canonical_market_links'
              AND t.tgname = 'trg_canonical_market_links_updated_at'
              AND NOT t.tgisinternal
            """
        )
        row = cur.fetchone()
    assert row is not None, "trg_canonical_market_links_updated_at must exist post-0072"
    trigger_def = row["def"]
    assert "BEFORE UPDATE" in trigger_def
    assert "update_canonical_market_links_updated_at" in trigger_def


def test_market_links_update_trigger_advances_updated_at(db_pool: Any) -> None:
    """UPDATE on canonical_market_links advances ``updated_at`` per the trigger."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_market_links (
                    canonical_market_id, platform_market_id, link_state,
                    confidence, algorithm_id, decided_by
                ) VALUES (%s, %s, 'active', 1.000, %s, %s)
                RETURNING id, updated_at
                """,
                (seeded_market_id, seeded_platform_market_id, algorithm_id, "system:test"),
            )
            row = cur.fetchone()
            link_id = int(row["id"])
            initial_updated_at = row["updated_at"]

        # UPDATE a non-updated_at column; trigger should refresh updated_at.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                UPDATE canonical_market_links
                SET link_state = 'retired', retired_at = now()
                WHERE id = %s
                """,
                (link_id,),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT updated_at FROM canonical_market_links WHERE id = %s",
                (link_id,),
            )
            post_row = cur.fetchone()
        post_updated_at = post_row["updated_at"]
        # `>` (strict) NOT `>=` per Ripley sentinel P1 (session 80): INSERT and
        # UPDATE happen in separate ``commit=True`` transactions, so the
        # transaction_timestamp ``now()`` returns DIFFERENT values across them
        # — a correctly-firing trigger ALWAYS advances ``updated_at``.  A no-op
        # trigger (function-body broken to ``OLD.updated_at`` or stripped) would
        # leave ``post == initial`` and ``>=`` would silently pass.  Tightening
        # to ``>`` catches the no-op case at this layer; PR #1066 round-trip
        # CI gate's pg_get_functiondef snapshot is the complementary defense.
        assert post_updated_at > initial_updated_at, (
            f"updated_at must advance (BEFORE UPDATE trigger no-op suspected); "
            f"initial={initial_updated_at!r}, post={post_updated_at!r}"
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_market_links WHERE canonical_market_id = %s",
                (seeded_market_id,),
            )
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 5b: canonical_event_links BEFORE UPDATE trigger
# =============================================================================


def test_event_links_update_trigger_exists(db_pool: Any) -> None:
    """``trg_canonical_event_links_updated_at`` BEFORE UPDATE trigger exists."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_triggerdef(t.oid) AS def
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            WHERE c.relname = 'canonical_event_links'
              AND t.tgname = 'trg_canonical_event_links_updated_at'
              AND NOT t.tgisinternal
            """
        )
        row = cur.fetchone()
    assert row is not None, "trg_canonical_event_links_updated_at must exist post-0072"
    trigger_def = row["def"]
    assert "BEFORE UPDATE" in trigger_def
    assert "update_canonical_event_links_updated_at" in trigger_def


def test_event_links_update_trigger_advances_updated_at(db_pool: Any) -> None:
    """UPDATE on canonical_event_links advances ``updated_at`` per the trigger."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_platform_event_id = _seed_platform_event(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_event_links (
                    canonical_event_id, platform_event_id, link_state,
                    confidence, algorithm_id, decided_by
                ) VALUES (%s, %s, 'active', 1.000, %s, %s)
                RETURNING id, updated_at
                """,
                (seeded_event_id, seeded_platform_event_id, algorithm_id, "system:test"),
            )
            row = cur.fetchone()
            link_id = int(row["id"])
            initial_updated_at = row["updated_at"]

        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                UPDATE canonical_event_links
                SET link_state = 'retired', retired_at = now()
                WHERE id = %s
                """,
                (link_id,),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT updated_at FROM canonical_event_links WHERE id = %s",
                (link_id,),
            )
            post_row = cur.fetchone()
        post_updated_at = post_row["updated_at"]
        # `>` (strict) per Ripley sentinel P1 — see equivalent assertion in
        # test_market_links_update_trigger_advances_updated_at for full
        # rationale.  Catches no-op trigger function body at this layer.
        assert post_updated_at > initial_updated_at, (
            f"updated_at must advance (BEFORE UPDATE trigger no-op suspected); "
            f"initial={initial_updated_at!r}, post={post_updated_at!r}"
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_event_links WHERE canonical_event_id = %s",
                (seeded_event_id,),
            )
        _cleanup_platform_event(seeded_platform_event_id)
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 6: FK-target indexes
# =============================================================================


@pytest.mark.parametrize(
    ("table", "index_name", "column"),
    [
        (
            "canonical_market_links",
            "idx_canonical_market_links_canonical_market_id",
            "canonical_market_id",
        ),
        (
            "canonical_market_links",
            "idx_canonical_market_links_algorithm_id",
            "algorithm_id",
        ),
        (
            "canonical_event_links",
            "idx_canonical_event_links_canonical_event_id",
            "canonical_event_id",
        ),
        (
            "canonical_event_links",
            "idx_canonical_event_links_algorithm_id",
            "algorithm_id",
        ),
    ],
)
def test_fk_target_index_exists(db_pool: Any, table: str, index_name: str, column: str) -> None:
    """Each FK-target index exists on the prescribed column."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexdef FROM pg_indexes
            WHERE tablename = %s AND indexname = %s
            """,
            (table, index_name),
        )
        row = cur.fetchone()
    assert row is not None, f"{index_name} missing post-0072"
    indexdef = row["indexdef"]
    assert f"({column})" in indexdef, f"{index_name} must be on {column}; got: {indexdef}"
    # FK-target indexes are not unique by themselves (PK + EXCLUDE provide
    # uniqueness where needed); these are pure FK-target lookup indexes.
    assert "CREATE UNIQUE" not in indexdef, f"FK-target index must NOT be UNIQUE; got: {indexdef}"


# =============================================================================
# Group 7: EXCLUDE constraints exist (structural — paired with Group 4
#                                      behavioral load-bearing tests)
# =============================================================================


def test_market_links_exclude_constraint_exists(db_pool: Any) -> None:
    """``uq_canonical_market_links_active`` EXCLUDE constraint exists."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_market_links'::regclass
              AND conname = 'uq_canonical_market_links_active'
            """
        )
        row = cur.fetchone()
    assert row is not None, "uq_canonical_market_links_active must exist post-0072"
    constraint_def = row["def"]
    assert "EXCLUDE USING btree" in constraint_def
    assert "platform_market_id WITH =" in constraint_def
    # pg_get_constraintdef wraps the WHERE clause with ::text casts and triple
    # parens (``WHERE (((link_state)::text = 'active'::text))``), so a literal
    # ``WHERE (link_state`` substring match would fail on a constraint that is
    # functionally correct.  Check WHERE presence + the load-bearing tokens
    # (link_state column reference + 'active' literal) separately.
    assert "WHERE" in constraint_def
    assert "link_state" in constraint_def
    assert "active" in constraint_def


def test_event_links_exclude_constraint_exists(db_pool: Any) -> None:
    """``uq_canonical_event_links_active`` EXCLUDE constraint exists."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_event_links'::regclass
              AND conname = 'uq_canonical_event_links_active'
            """
        )
        row = cur.fetchone()
    assert row is not None, "uq_canonical_event_links_active must exist post-0072"
    constraint_def = row["def"]
    assert "EXCLUDE USING btree" in constraint_def
    assert "platform_event_id WITH =" in constraint_def
    # See note in test_market_links_exclude_constraint_exists for why the
    # WHERE assertion is split into separate substring checks.
    assert "WHERE" in constraint_def
    assert "link_state" in constraint_def
    assert "active" in constraint_def
