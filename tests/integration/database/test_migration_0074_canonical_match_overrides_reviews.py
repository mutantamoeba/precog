"""Integration tests for migration 0074 — Cohort 3 canonical_match_overrides + canonical_match_reviews.

Verifies the POST-MIGRATION state of the two operational-state tables
introduced by migration 0074 — Cohort 3 final slot, **closing Cohort 3**.
Per session-78 5-slot adjudication (ADR-118 v2.41 amendment) +
session-80 S82 design-stage P41 council inheritance + session-82 PM
build spec + Holden re-engagement memo
(``memory/build_spec_0074_pm_memo.md`` +
``memory/holden_reengagement_0074_memo.md``).

Test groups:
    - Column shape: per-column type / nullability / default / max-length
      with mirror-symmetric f-string assertion messages from day 1
      (#1085 finding #4 + #11 inheritance — both tables ship symmetric
      f-strings).
    - CHECK constraints: review_state 4-value vocab + polarity 2-value
      vocab + polarity-pairing conditional + reason-nonempty all fire
      when violated (Ripley false-pass-hunt frame: BOTH polarity-pairing
      branches exercised).
    - UNIQUE constraint: at most one override per platform_market_id;
      DELETE-then-INSERT replace flow (Holden Item 2 P2).
    - FK / ON DELETE: link_id CASCADE on reviews; platform_market_id
      CASCADE on overrides; canonical_market_id RESTRICT on overrides.
      Pre-condition assertions on every CASCADE/RESTRICT test (#1085 #14
      inheritance).
    - Indexes: 6 indexes (3 per table) all present with correct partial
      WHERE clauses + DESC direction where applicable (#1085 #18
      inheritance).
    - Pattern 73 SSOT bidirectional oracle: pg_constraint introspection
      asserts CHECK lists match Python constants (#1085 #15 inheritance).
    - manual_v1-on-human-decided-actions convention living-example tests
      (#1085 #16 inheritance + Holden Item 1 P1 bidirectional anchoring):
      JOIN to match_algorithm + decided_by 'human:%' assertion for all
      3 covered actions (override, review_approve, review_reject).
    - Slot-0073 deferred test (per #1085 #12, naturally landing in slot
      0074): ``test_canonical_match_log_get_match_log_for_link_include
      _orphans_round_trip`` exercises the orphan path via
      transition_review (which writes a log row that survives link
      deletion via SET NULL).

Issue: Epic #972 (Canonical Layer Foundation — Phase B.5),
    #1058 (P41 design-stage codification — slot 0074 is the fifth and
    final Cohort 3 builder dispatch under Tier 0 + S82),
    #1085 (slot-0074 polish-item inheritance — closes 11 of 19 items
    directly + structural-mindset inheritance for the rest)
ADR: ADR-118 v2.41 + v2.42 + v2.42 sub-amendment B
Build spec: ``memory/build_spec_0074_pm_memo.md``
Holden re-engagement: ``memory/holden_reengagement_0074_memo.md``

Markers:
    @pytest.mark.integration: real DB required.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import psycopg2
import psycopg2.errors
import pytest

from precog.database.connection import get_cursor
from precog.database.constants import POLARITY_VALUES, REVIEW_STATE_VALUES
from precog.database.crud_canonical_match_log import (
    append_match_log_row,
    get_match_log_for_link,
)
from precog.database.crud_canonical_match_overrides import (
    create_override,
    delete_override,
)
from precog.database.crud_canonical_match_reviews import (
    create_review,
    transition_review,
)
from tests.integration.database._canonical_event_helpers import (
    _cleanup_canonical_event,
    _seed_canonical_event,
)
from tests.integration.database._canonical_market_helpers import (
    _cleanup_canonical_market,
    _cleanup_canonical_market_link,
    _cleanup_platform_market,
    _get_manual_v1_algorithm_id,
    _seed_canonical_market,
    _seed_canonical_market_link,
    _seed_platform_market,
)

pytestmark = [pytest.mark.integration]


# =============================================================================
# Per-column shape spec (mirrors migration 0074 DDL verbatim).
#
# Each tuple: (column_name, data_type, is_nullable, default_substring_or_None,
#              max_char_length_or_None).
# Mirror-symmetric assertion messages per #1085 finding #4 + #11.
# =============================================================================

_REVIEWS_COLS: list[tuple[str, str, str, str | None, int | None]] = [
    ("id", "bigint", "NO", "nextval", None),
    ("link_id", "bigint", "NO", None, None),
    ("review_state", "character varying", "NO", None, 16),
    ("reviewer", "character varying", "YES", None, 64),
    ("reviewed_at", "timestamp with time zone", "YES", None, None),
    ("flagged_reason", "character varying", "YES", None, 256),
    ("created_at", "timestamp with time zone", "NO", "now()", None),
]

_OVERRIDES_COLS: list[tuple[str, str, str, str | None, int | None]] = [
    ("id", "bigint", "NO", "nextval", None),
    ("platform_market_id", "integer", "NO", None, None),
    ("canonical_market_id", "bigint", "YES", None, None),
    ("polarity", "character varying", "NO", None, 16),
    ("reason", "text", "NO", None, None),
    ("created_by", "character varying", "NO", None, 64),
    ("created_at", "timestamp with time zone", "NO", "now()", None),
]


# =============================================================================
# Group 1: column shape (mirror-symmetric f-string assertions per #1085 #4 + #11)
# =============================================================================


@pytest.mark.parametrize(
    ("col_name", "data_type", "is_nullable", "default_substr", "max_char_len"),
    _REVIEWS_COLS,
)
def test_canonical_match_reviews_column_shape(
    db_pool: Any,
    col_name: str,
    data_type: str,
    is_nullable: str,
    default_substr: str | None,
    max_char_len: int | None,
) -> None:
    """Each column on canonical_match_reviews has the migration-prescribed shape.

    #1085 finding #4 + #11 inheritance: assertion messages are detailed
    f-strings, mirror-symmetric across both shape tests on the two
    sibling tables.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT data_type, is_nullable, column_default, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'canonical_match_reviews'
              AND column_name = %s
              AND table_schema = 'public'
            """,
            (col_name,),
        )
        row = cur.fetchone()
    assert row is not None, (
        f"canonical_match_reviews.{col_name} missing post-0074 — expected per migration DDL"
    )
    assert row["data_type"] == data_type, (
        f"canonical_match_reviews.{col_name} type mismatch: "
        f"expected {data_type!r}, got {row['data_type']!r}"
    )
    assert row["is_nullable"] == is_nullable, (
        f"canonical_match_reviews.{col_name} nullability mismatch: "
        f"expected {is_nullable!r}, got {row['is_nullable']!r}"
    )
    if default_substr is not None:
        actual_default = row["column_default"] or ""
        assert default_substr.lower() in actual_default.lower(), (
            f"canonical_match_reviews.{col_name} default missing "
            f"{default_substr!r}; got {actual_default!r}"
        )
    if max_char_len is not None:
        assert row["character_maximum_length"] == max_char_len, (
            f"canonical_match_reviews.{col_name} max_length mismatch: "
            f"expected {max_char_len}, got {row['character_maximum_length']}"
        )


@pytest.mark.parametrize(
    ("col_name", "data_type", "is_nullable", "default_substr", "max_char_len"),
    _OVERRIDES_COLS,
)
def test_canonical_match_overrides_column_shape(
    db_pool: Any,
    col_name: str,
    data_type: str,
    is_nullable: str,
    default_substr: str | None,
    max_char_len: int | None,
) -> None:
    """Each column on canonical_match_overrides has the migration-prescribed shape.

    Mirror-symmetric assertion messages with
    test_canonical_match_reviews_column_shape per #1085 #11.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT data_type, is_nullable, column_default, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'canonical_match_overrides'
              AND column_name = %s
              AND table_schema = 'public'
            """,
            (col_name,),
        )
        row = cur.fetchone()
    assert row is not None, (
        f"canonical_match_overrides.{col_name} missing post-0074 — expected per migration DDL"
    )
    assert row["data_type"] == data_type, (
        f"canonical_match_overrides.{col_name} type mismatch: "
        f"expected {data_type!r}, got {row['data_type']!r}"
    )
    assert row["is_nullable"] == is_nullable, (
        f"canonical_match_overrides.{col_name} nullability mismatch: "
        f"expected {is_nullable!r}, got {row['is_nullable']!r}"
    )
    if default_substr is not None:
        actual_default = row["column_default"] or ""
        assert default_substr.lower() in actual_default.lower(), (
            f"canonical_match_overrides.{col_name} default missing "
            f"{default_substr!r}; got {actual_default!r}"
        )
    if max_char_len is not None:
        assert row["character_maximum_length"] == max_char_len, (
            f"canonical_match_overrides.{col_name} max_length mismatch: "
            f"expected {max_char_len}, got {row['character_maximum_length']}"
        )


# =============================================================================
# Group 2: CHECK constraints fire when violated
# =============================================================================


@pytest.mark.parametrize(
    "bad_review_state",
    # All values stay <= 16 chars (the VARCHAR(16) column boundary) so
    # the CheckViolation is the failure mode under test, not a
    # StringDataRightTruncation pre-empt.
    ["bad_state", "PENDING", "done", "draft", "rev_pending", ""],
    ids=lambda s: f"bad_review_state_{s or 'EMPTY'}",
)
def test_review_state_check_fires_on_invalid_value(db_pool: Any, bad_review_state: str) -> None:
    """INSERT with various invalid review_state values raises CheckViolation.

    Per Ripley F6 P2 (#1095 close-out): parametrized over multiple bad
    values for defense-in-depth alongside the bidirectional oracle in
    Group 5.  Catches a hypothetical world where the DDL CHECK accepts
    a single value the test happens to feed (extreme edge case but the
    parametrize cost is trivial).
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()
    seeded_link_id = _seed_canonical_market_link(
        seeded_market_id, seeded_platform_market_id, algorithm_id
    )

    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_match_reviews (link_id, review_state)
                    VALUES (%s, %s)
                    """,
                    (seeded_link_id, bad_review_state),
                )
    finally:
        _cleanup_canonical_market_link(seeded_link_id)
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


@pytest.mark.parametrize(
    "bad_polarity",
    # All values stay <= 16 chars (the VARCHAR(16) column boundary) so
    # the CheckViolation is the failure mode under test, not a
    # StringDataRightTruncation pre-empt.
    ["WRONG", "must_match", "MUST", "match", "either", ""],
    ids=lambda s: f"bad_polarity_{s or 'EMPTY'}",
)
def test_polarity_check_fires_on_invalid_value(db_pool: Any, bad_polarity: str) -> None:
    """INSERT with various invalid polarity values raises CheckViolation.

    Per Ripley F6 P2 (#1095 close-out): parametrized over multiple bad
    values for defense-in-depth alongside the bidirectional oracle in
    Group 5.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)

    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_match_overrides (
                        platform_market_id, canonical_market_id, polarity,
                        reason, created_by
                    ) VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        seeded_platform_market_id,
                        seeded_market_id,
                        bad_polarity,
                        "test reason",
                        "human:test",
                    ),
                )
    finally:
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_polarity_pairing_check_fires_must_match_with_null_canonical(
    db_pool: Any,
) -> None:
    """**LOAD-BEARING** per build spec § 2 + Ripley false-pass-hunt frame.

    Direct-SQL INSERT with polarity='MUST_MATCH' AND canonical_market_id IS
    NULL raises CheckViolation (DDL CHECK is defense-in-depth; CRUD
    layer's polarity-pairing rule is the primary defense, exercised in
    unit tests).
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)

    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_match_overrides (
                        platform_market_id, canonical_market_id, polarity,
                        reason, created_by
                    ) VALUES (%s, NULL, 'MUST_MATCH', %s, %s)
                    """,
                    (seeded_platform_market_id, "bad pairing", "human:test"),
                )
    finally:
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_polarity_pairing_check_fires_must_not_match_with_non_null_canonical(
    db_pool: Any,
) -> None:
    """**LOAD-BEARING** per build spec § 2 + Ripley false-pass-hunt frame.

    Direct-SQL INSERT with polarity='MUST_NOT_MATCH' AND canonical_market_id
    NOT NULL raises CheckViolation.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)

    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_match_overrides (
                        platform_market_id, canonical_market_id, polarity,
                        reason, created_by
                    ) VALUES (%s, %s, 'MUST_NOT_MATCH', %s, %s)
                    """,
                    (
                        seeded_platform_market_id,
                        seeded_market_id,
                        "bad pairing",
                        "human:test",
                    ),
                )
    finally:
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_polarity_pairing_check_passes_must_match_with_canonical(
    db_pool: Any,
) -> None:
    """Happy path: polarity='MUST_MATCH' + canonical_market_id NOT NULL succeeds.

    Per Ripley F5 P2 (#1095 close-out): happy-path INSERT is followed by
    a SELECT-back of (polarity, canonical_market_id) to verify the
    persisted row matches the input — closes the false-pass surface
    where an INSERT with mis-bound parameters could succeed at the SQL
    level but persist a different row than the test inputs intended.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    override_id: int | None = None

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_match_overrides (
                    platform_market_id, canonical_market_id, polarity,
                    reason, created_by
                ) VALUES (%s, %s, 'MUST_MATCH', %s, %s)
                RETURNING id
                """,
                (
                    seeded_platform_market_id,
                    seeded_market_id,
                    "happy path",
                    "human:test",
                ),
            )
            override_id = int(cur.fetchone()["id"])
        assert override_id is not None, (
            "happy path INSERT with MUST_MATCH + canonical_market_id NOT NULL "
            "should succeed; got no row id"
        )

        # Round-trip SELECT-back to verify the persisted polarity +
        # canonical_market_id exactly match the inputs (Ripley F5 P2).
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT polarity, canonical_market_id
                FROM canonical_match_overrides
                WHERE id = %s
                """,
                (override_id,),
            )
            persisted = cur.fetchone()
        assert persisted is not None, (
            f"SELECT-back failed: override id={override_id} should exist immediately after INSERT"
        )
        assert persisted["polarity"] == "MUST_MATCH", (
            f"persisted polarity drift: expected 'MUST_MATCH', got {persisted['polarity']!r}"
        )
        assert persisted["canonical_market_id"] == seeded_market_id, (
            f"persisted canonical_market_id drift: expected "
            f"{seeded_market_id}, got {persisted['canonical_market_id']!r}"
        )
    finally:
        if override_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM canonical_match_overrides WHERE id = %s",
                    (override_id,),
                )
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_polarity_pairing_check_passes_must_not_match_with_null_canonical(
    db_pool: Any,
) -> None:
    """Happy path: polarity='MUST_NOT_MATCH' + canonical_market_id IS NULL succeeds.

    Per Ripley F5 P2 (#1095 close-out): SELECT-back round-trip verifies
    polarity + canonical_market_id exactly.  Per Glokta Nit 8 (#1095
    close-out): canonical_market is intentionally NOT seeded for this
    test branch — MUST_NOT_MATCH overrides have canonical_market_id=NULL
    by design, so seeding a canonical_market here would be cosmetic
    asymmetry not a load-bearing precondition.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_platform_market_id = _seed_platform_market(suffix)
    override_id: int | None = None

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_match_overrides (
                    platform_market_id, canonical_market_id, polarity,
                    reason, created_by
                ) VALUES (%s, NULL, 'MUST_NOT_MATCH', %s, %s)
                RETURNING id
                """,
                (seeded_platform_market_id, "happy path", "human:test"),
            )
            override_id = int(cur.fetchone()["id"])
        assert override_id is not None, (
            "happy path INSERT with MUST_NOT_MATCH + NULL canonical_market_id "
            "should succeed; got no row id"
        )

        # Round-trip SELECT-back (Ripley F5 P2).
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT polarity, canonical_market_id
                FROM canonical_match_overrides
                WHERE id = %s
                """,
                (override_id,),
            )
            persisted = cur.fetchone()
        assert persisted is not None, (
            f"SELECT-back failed: override id={override_id} should exist immediately after INSERT"
        )
        assert persisted["polarity"] == "MUST_NOT_MATCH", (
            f"persisted polarity drift: expected 'MUST_NOT_MATCH', got {persisted['polarity']!r}"
        )
        assert persisted["canonical_market_id"] is None, (
            f"persisted canonical_market_id drift: MUST_NOT_MATCH polarity "
            f"requires NULL, got {persisted['canonical_market_id']!r}"
        )
    finally:
        if override_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM canonical_match_overrides WHERE id = %s",
                    (override_id,),
                )
        _cleanup_platform_market(seeded_platform_market_id)


def test_reason_nonempty_check_fires_empty_string(db_pool: Any) -> None:
    """DDL CHECK ck_canonical_match_overrides_reason_nonempty fires on empty string."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)

    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_match_overrides (
                        platform_market_id, canonical_market_id, polarity,
                        reason, created_by
                    ) VALUES (%s, %s, 'MUST_MATCH', '', %s)
                    """,
                    (seeded_platform_market_id, seeded_market_id, "human:test"),
                )
    finally:
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_reason_nonempty_check_fires_spaces_only_per_pg_trim_semantics(
    db_pool: Any,
) -> None:
    """DDL CHECK fires on space-only reason (length(trim(reason)) > 0).

    Renamed from test_reason_nonempty_check_fires_whitespace_only per
    Ripley F1 P1 finding (slot 0074 review): the prior name overclaimed
    "whitespace_only" but the test only exercises 8 spaces, which is
    what PostgreSQL's default ``trim(text)`` actually catches.

    Note: PostgreSQL's default ``trim(text)`` strips only the space
    character, NOT the broader Python ``str.strip()`` set (which includes
    ``\\t`` / ``\\n``).  The DDL CHECK uses ``length(trim(reason)) > 0``;
    this test exercises the spaces-only branch that the DDL guard
    catches.

    The broader whitespace-only case (tabs, newlines, mixed) is the
    CRUD-layer's responsibility per the spec's defense-in-depth framing
    — Python's ``reason.strip() == ""`` catches all unicode whitespace;
    the DDL CHECK is the secondary guard for direct-SQL bypass with
    naive empty-or-spaces input.  See the positive-divergence test
    ``test_reason_tabs_only_passes_ddl_check_but_crud_rejects`` below
    for the documented intentional asymmetry.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)

    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_match_overrides (
                        platform_market_id, canonical_market_id, polarity,
                        reason, created_by
                    ) VALUES (%s, %s, 'MUST_MATCH', %s, %s)
                    """,
                    (
                        seeded_platform_market_id,
                        seeded_market_id,
                        "        ",  # 8 spaces — DDL trim() strips spaces
                        "human:test",
                    ),
                )
    finally:
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_reason_tabs_only_passes_ddl_check_but_crud_rejects(db_pool: Any) -> None:
    """Documents the intentional CRUD-vs-DDL asymmetry on whitespace.

    Per Ripley F1 P1 finding (slot 0074 review): PostgreSQL's
    ``trim(text)`` defaults to stripping the space character only, so
    ``length(trim(E'\\t\\n')) > 0`` — the DDL CHECK ACCEPTS tabs and
    newlines.  The CRUD layer's ``reason.strip() == ''`` check (Python's
    broader whitespace set) catches them.

    This test asserts the divergence is intentional and bounded:
        * Direct-SQL bypass with tabs/newlines IS accepted by the DDL
          CHECK ``length(trim(reason)) > 0`` (PostgreSQL trim semantics).
        * The CRUD path ``create_override`` rejects with ValueError
          (Python ``str.strip()`` semantics).

    The asymmetry is intentional defense-in-depth: Python is the primary
    defense (catches all unicode whitespace); the DDL CHECK is the
    secondary guard against direct-SQL bypass with naive empty-or-spaces
    input.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    inserted_override_id: int | None = None

    try:
        # Direct-SQL INSERT with tabs/newlines reason — DDL CHECK accepts.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_match_overrides (
                    platform_market_id, canonical_market_id, polarity,
                    reason, created_by
                ) VALUES (%s, %s, 'MUST_MATCH', %s, %s)
                RETURNING id
                """,
                (
                    seeded_platform_market_id,
                    seeded_market_id,
                    "\t\n",  # tabs + newline — Python strip() == "" but pg trim() does NOT strip these
                    "human:test",
                ),
            )
            inserted_override_id = int(cur.fetchone()["id"])
        assert inserted_override_id is not None, (
            "DDL CHECK contract violated: direct-SQL INSERT with tabs/newlines "
            "reason should be accepted by the DDL (pg trim() strips space char only)"
        )

        # CRUD call with same reason — raises ValueError BEFORE SQL.
        with pytest.raises(ValueError, match="cannot be empty"):
            create_override(
                platform_market_id=seeded_platform_market_id + 1,  # avoid UNIQUE collision
                canonical_market_id=seeded_market_id,
                polarity="MUST_MATCH",
                reason="\t\n",
                created_by="human:test",
            )
    finally:
        if inserted_override_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM canonical_match_overrides WHERE id = %s",
                    (inserted_override_id,),
                )
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 3: FK / ON DELETE tests (#1085 #14 inheritance — pre-condition asserts)
# =============================================================================


def test_canonical_match_reviews_link_id_cascade_on_delete(db_pool: Any) -> None:
    """**LOAD-BEARING** per build spec § 6.

    DELETE link → review row gone (CASCADE).  Pre-condition assertion
    proves the review row was actually present before DELETE per #1085
    finding #14 inheritance.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()
    seeded_link_id = _seed_canonical_market_link(
        seeded_market_id, seeded_platform_market_id, algorithm_id
    )
    review_id: int | None = None

    try:
        review_id = create_review(link_id=seeded_link_id)

        # Pre-condition: review row exists and references the seeded link.
        with get_cursor() as cur:
            cur.execute(
                "SELECT link_id FROM canonical_match_reviews WHERE id = %s",
                (review_id,),
            )
            pre_row = cur.fetchone()
        assert pre_row is not None, (
            f"pre-condition: review row id={review_id} should exist before link DELETE; got NULL"
        )
        assert pre_row["link_id"] == seeded_link_id, (
            f"pre-condition: review row should reference link_id={seeded_link_id}, "
            f"got {pre_row['link_id']!r}"
        )

        # DELETE the link — CASCADE must fire on canonical_match_reviews.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_market_links WHERE id = %s",
                (seeded_link_id,),
            )

        # Post-condition: review row gone.
        with get_cursor() as cur:
            cur.execute(
                "SELECT id FROM canonical_match_reviews WHERE id = %s",
                (review_id,),
            )
            post_row = cur.fetchone()
        assert post_row is None, (
            f"CASCADE contract violated — review row id={review_id} should be "
            f"deleted by link DELETE; got {post_row!r}"
        )
        review_id = None  # already cascaded
    finally:
        if review_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM canonical_match_reviews WHERE id = %s",
                    (review_id,),
                )
        # Defensive idempotent cleanup of the link.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_market_links WHERE id = %s",
                (seeded_link_id,),
            )
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_match_overrides_platform_market_id_cascade_on_delete(
    db_pool: Any,
) -> None:
    """**LOAD-BEARING** per build spec § 6.

    DELETE markets row → override row gone (CASCADE).  Pre-condition
    assertion proves the override existed before DELETE.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    override_id: int | None = None

    try:
        # Use direct INSERT (not create_override) so this test is independent
        # of the CRUD-layer log-row write side-effect.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_match_overrides (
                    platform_market_id, canonical_market_id, polarity,
                    reason, created_by
                ) VALUES (%s, %s, 'MUST_MATCH', %s, %s)
                RETURNING id
                """,
                (
                    seeded_platform_market_id,
                    seeded_market_id,
                    "test override",
                    "human:test",
                ),
            )
            override_id = int(cur.fetchone()["id"])

        # Pre-condition: override row exists and references the seeded platform.
        with get_cursor() as cur:
            cur.execute(
                "SELECT platform_market_id FROM canonical_match_overrides WHERE id = %s",
                (override_id,),
            )
            pre_row = cur.fetchone()
        assert pre_row is not None, (
            f"pre-condition: override row id={override_id} should exist before "
            f"platform DELETE; got NULL"
        )
        assert pre_row["platform_market_id"] == seeded_platform_market_id, (
            f"pre-condition: override should reference platform_market_id="
            f"{seeded_platform_market_id}, got {pre_row['platform_market_id']!r}"
        )

        # DELETE the platform market — CASCADE must fire.
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM markets WHERE id = %s", (seeded_platform_market_id,))

        with get_cursor() as cur:
            cur.execute(
                "SELECT id FROM canonical_match_overrides WHERE id = %s",
                (override_id,),
            )
            post_row = cur.fetchone()
        assert post_row is None, (
            f"CASCADE contract violated — override id={override_id} should be "
            f"deleted by platform DELETE; got {post_row!r}"
        )
        override_id = None
    finally:
        if override_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM canonical_match_overrides WHERE id = %s",
                    (override_id,),
                )
        # platform market already cascaded; cleanup canonical_market + event.
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_match_overrides_canonical_market_id_restrict_blocks_canonical_delete(
    db_pool: Any,
) -> None:
    """**LOAD-BEARING** per build spec § 6.

    A canonical_markets row pointed at by a MUST_MATCH override CANNOT
    be deleted; psycopg2 surfaces RestrictViolation.

    Pre-condition assertion (#1085 #14): override row exists pointing
    at the canonical row before DELETE attempt.

    override_id pre-initialized to None per #1085 #2 + #6 + #8
    UnboundLocalError pattern.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    override_id: int | None = None

    try:
        # Insert via direct SQL (independent of CRUD-layer log-write).
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_match_overrides (
                    platform_market_id, canonical_market_id, polarity,
                    reason, created_by
                ) VALUES (%s, %s, 'MUST_MATCH', %s, %s)
                RETURNING id
                """,
                (
                    seeded_platform_market_id,
                    seeded_market_id,
                    "test override",
                    "human:test",
                ),
            )
            override_id = int(cur.fetchone()["id"])

        # Pre-condition: override row exists pointing at the canonical_market.
        with get_cursor() as cur:
            cur.execute(
                "SELECT canonical_market_id FROM canonical_match_overrides WHERE id = %s",
                (override_id,),
            )
            pre_row = cur.fetchone()
        assert pre_row is not None, (
            f"pre-condition: override row id={override_id} should exist before "
            f"canonical DELETE attempt"
        )
        assert pre_row["canonical_market_id"] == seeded_market_id, (
            f"pre-condition: override should reference canonical_market_id="
            f"{seeded_market_id}, got {pre_row['canonical_market_id']!r}"
        )

        # Pre-condition: canonical_markets row exists immediately before
        # DELETE attempt (Ripley F10 P2 — symmetric pre-condition pattern
        # per #1085 #14 inheritance).  Without this, the test could
        # silently false-pass if the canonical_markets row was already
        # gone — the DELETE would match 0 rows but RESTRICT only fires
        # when there IS a row to delete.
        with get_cursor() as cur:
            cur.execute(
                "SELECT id FROM canonical_markets WHERE id = %s",
                (seeded_market_id,),
            )
            canonical_row = cur.fetchone()
        assert canonical_row is not None, (
            f"pre-condition: canonical_markets row id={seeded_market_id} "
            f"should exist immediately before RESTRICT DELETE attempt; got "
            f"NULL.  Without this row, DELETE would silently match 0 rows "
            f"and the test would false-pass on a no-op."
        )

        # DELETE canonical_markets row — RESTRICT must fire.
        with pytest.raises(
            (psycopg2.errors.ForeignKeyViolation, psycopg2.errors.RestrictViolation)
        ):
            with get_cursor(commit=True) as cur:
                cur.execute("DELETE FROM canonical_markets WHERE id = %s", (seeded_market_id,))
    finally:
        if override_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM canonical_match_overrides WHERE id = %s",
                    (override_id,),
                )
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 4: UNIQUE constraint + replace flow (Holden Item 2 P2)
# =============================================================================


def test_canonical_match_overrides_unique_platform_market_id(db_pool: Any) -> None:
    """Second INSERT on same platform_market_id raises UniqueViolation."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    override_id: int | None = None

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_match_overrides (
                    platform_market_id, canonical_market_id, polarity,
                    reason, created_by
                ) VALUES (%s, %s, 'MUST_MATCH', %s, %s)
                RETURNING id
                """,
                (
                    seeded_platform_market_id,
                    seeded_market_id,
                    "first override",
                    "human:test",
                ),
            )
            override_id = int(cur.fetchone()["id"])

        # Second INSERT on the same platform_market_id must raise.
        with pytest.raises(psycopg2.errors.UniqueViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_match_overrides (
                        platform_market_id, canonical_market_id, polarity,
                        reason, created_by
                    ) VALUES (%s, NULL, 'MUST_NOT_MATCH', %s, %s)
                    """,
                    (
                        seeded_platform_market_id,
                        "duplicate override",
                        "human:test",
                    ),
                )
    finally:
        if override_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM canonical_match_overrides WHERE id = %s",
                    (override_id,),
                )
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_match_overrides_replace_via_delete_then_insert_atomic(
    db_pool: Any,
) -> None:
    """**LOAD-BEARING** per Holden re-engagement Item 2 (P2).

    The documented operator-runbook flow: replace MUST_NOT_MATCH override
    A with MUST_MATCH override B via delete_override(A) +
    create_override(B).  Asserts:
      (1) one row in canonical_match_overrides (B);
      (2) three rows in canonical_match_log with action='override' (A's
          create + A's delete + B's create);
      (3) neither operation raised.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    override_a_id: int | None = None
    override_b_id: int | None = None

    try:
        # Capture log row count BEFORE the test starts so we can assert
        # delta=3 after the create-A + delete-A + create-B flow completes.
        # Per Ripley Nit 1 (#1095 close-out): COUNT query lives INSIDE the
        # try block so a query failure (e.g., aborted transaction state)
        # routes to the finally cleanup rather than bypassing it.
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS cnt FROM canonical_match_log
                WHERE platform_market_id = %s AND action = 'override'
                """,
                (seeded_platform_market_id,),
            )
            log_count_before = int(cur.fetchone()["cnt"])

        # Create override A (MUST_NOT_MATCH).
        override_a_id = create_override(
            platform_market_id=seeded_platform_market_id,
            canonical_market_id=None,
            polarity="MUST_NOT_MATCH",
            reason="initial assertion: not in any canonical group",
            created_by="human:test",
        )

        # Replace: DELETE A then INSERT B (MUST_MATCH, with canonical pointer).
        delete_override(
            override_a_id,
            deleted_by="human:test",
            reason="operator changed mind; market IS in a canonical group",
        )
        override_a_id = None  # already deleted

        override_b_id = create_override(
            platform_market_id=seeded_platform_market_id,
            canonical_market_id=seeded_market_id,
            polarity="MUST_MATCH",
            reason="replacement: confirmed canonical pointer",
            created_by="human:test",
        )

        # Assertion 1: exactly one override row.
        with get_cursor() as cur:
            cur.execute(
                "SELECT id, polarity FROM canonical_match_overrides WHERE platform_market_id = %s",
                (seeded_platform_market_id,),
            )
            override_rows = cur.fetchall()
        assert len(override_rows) == 1, (
            f"after replace flow expected 1 override row, got {len(override_rows)}"
        )
        assert override_rows[0]["polarity"] == "MUST_MATCH", (
            f"after replace flow expected polarity='MUST_MATCH', got "
            f"{override_rows[0]['polarity']!r}"
        )

        # Assertion 2: three log rows with action='override' (delta from
        # the baseline pre-test count): create A + delete A + create B.
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS cnt FROM canonical_match_log
                WHERE platform_market_id = %s AND action = 'override'
                """,
                (seeded_platform_market_id,),
            )
            log_count_after = int(cur.fetchone()["cnt"])
        assert log_count_after - log_count_before == 3, (
            f"expected exactly 3 new log rows with action='override' "
            f"(create A + delete A + create B); got "
            f"delta={log_count_after - log_count_before}"
        )
    finally:
        if override_b_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM canonical_match_overrides WHERE id = %s",
                    (override_b_id,),
                )
        if override_a_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM canonical_match_overrides WHERE id = %s",
                    (override_a_id,),
                )
        # Cleanup the log rows the test created so subsequent runs are clean.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                DELETE FROM canonical_match_log
                WHERE platform_market_id = %s AND action = 'override'
                """,
                (seeded_platform_market_id,),
            )
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 5: Pattern 73 SSOT bidirectional oracle (#1085 #15 inheritance)
# =============================================================================


def _extract_check_in_values(check_def: str) -> set[str]:
    """Extract single-quoted vocabulary values from an ANY(ARRAY[...]) CHECK.

    Scoped to the ANY(ARRAY[...]) shape per Ripley F2 P1 finding on slot
    0074 review — fails loudly if the CHECK shape diverges (rather than
    silently extracting wrong strings from a hypothetical compound CHECK
    like ``review_state IN (...) AND reviewer ~ '...'``).

    PostgreSQL's ``pg_get_constraintdef`` may emit either of these shapes:
        ``ANY (ARRAY['a', 'b']::text[])``
        ``ANY ((ARRAY['a', 'b'])::text[])``
    The regex tolerates both via the optional inner ``(``.

    Example input: "CHECK (review_state::text = ANY (ARRAY['pending'::character
    varying, 'approved'::character varying, ...]::text[]))"
    Returns: {'pending', 'approved', ...}.
    """
    array_match = re.search(r"ANY \(\(?ARRAY\[([^\]]+)\]", check_def)
    if array_match is None:
        raise AssertionError(
            f"_extract_check_in_values expects ANY(ARRAY[...]) CHECK shape; "
            f"got constraint definition: {check_def!r}"
        )
    return set(re.findall(r"'([^']+)'", array_match.group(1)))


def test_canonical_match_reviews_review_state_check_matches_python_constant(
    db_pool: Any,
) -> None:
    """**LOAD-BEARING** per #1085 #15 (DDL-CHECK reverse-drift coverage).

    Introspect pg_constraint for the review_state CHECK; parse the IN list;
    assert ``set(REVIEW_STATE_VALUES) == set(values_in_check)``.  Catches
    BOTH directions of drift between the Python constant and the DDL.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conname = 'ck_canonical_match_reviews_review_state'
            """
        )
        row = cur.fetchone()
    assert row is not None, "ck_canonical_match_reviews_review_state CHECK not found post-0074"
    in_values = _extract_check_in_values(row["def"])
    assert in_values == set(REVIEW_STATE_VALUES), (
        f"Pattern 73 SSOT lockstep failure: REVIEW_STATE_VALUES drift detected. "
        f"Python constant: {set(REVIEW_STATE_VALUES)!r}; "
        f"DDL CHECK: {in_values!r}"
    )


def test_canonical_match_overrides_polarity_check_matches_python_constant(
    db_pool: Any,
) -> None:
    """**LOAD-BEARING** per #1085 #15 (DDL-CHECK reverse-drift coverage).

    Introspect pg_constraint for the polarity CHECK; parse the IN list;
    assert ``set(POLARITY_VALUES) == set(values_in_check)``.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conname = 'ck_canonical_match_overrides_polarity'
            """
        )
        row = cur.fetchone()
    assert row is not None, "ck_canonical_match_overrides_polarity CHECK not found post-0074"
    in_values = _extract_check_in_values(row["def"])
    assert in_values == set(POLARITY_VALUES), (
        f"Pattern 73 SSOT lockstep failure: POLARITY_VALUES drift detected. "
        f"Python constant: {set(POLARITY_VALUES)!r}; "
        f"DDL CHECK: {in_values!r}"
    )


# =============================================================================
# Group 6: manual_v1-on-human-decided-actions convention living-example tests
# (#1085 #16 + Holden Item 1 P1 bidirectional anchoring)
# =============================================================================


def test_canonical_match_overrides_create_writes_log_with_manual_v1_join(
    db_pool: Any,
) -> None:
    """**LOAD-BEARING** per #1085 #16 + Holden Item 1 P1 bidirectional anchoring.

    INSERT override via CRUD → SELECT log row → JOIN to match_algorithm
    → assert ``name='manual_v1'`` AND ``decided_by`` startswith 'human:'.

    The convention is observable from the LOG read-back, not just
    enforced at the CRUD-call site.  Living-doc by test name; regression
    catch if manual_v1 ever removed from seed OR if the override CRUD
    path stops writing the convention.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    override_id: int | None = None

    try:
        override_id = create_override(
            platform_market_id=seeded_platform_market_id,
            canonical_market_id=seeded_market_id,
            polarity="MUST_MATCH",
            reason="convention living-example test",
            created_by="human:eric",
        )

        # SELECT the log row + JOIN to match_algorithm.
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT cml.action, cml.decided_by, cml.algorithm_id,
                       ma.name AS algorithm_name, ma.version AS algorithm_version
                FROM canonical_match_log cml
                JOIN match_algorithm ma ON ma.id = cml.algorithm_id
                WHERE cml.platform_market_id = %s
                  AND cml.action = 'override'
                ORDER BY cml.decided_at DESC
                LIMIT 1
                """,
                (seeded_platform_market_id,),
            )
            log_row = cur.fetchone()
        assert log_row is not None, (
            "convention violated: no canonical_match_log row found for the "
            "override that was just created"
        )
        assert log_row["action"] == "override"
        assert log_row["algorithm_name"] == "manual_v1", (
            f"manual_v1-on-human-decided-actions convention violated: "
            f"expected algorithm name='manual_v1', got "
            f"{log_row['algorithm_name']!r}"
        )
        assert log_row["algorithm_version"] == "1.0.0"
        assert log_row["decided_by"].startswith("human:"), (
            f"human-only invariant violated at LOG read-back: "
            f"decided_by={log_row['decided_by']!r} should start with 'human:'"
        )
    finally:
        if override_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM canonical_match_overrides WHERE id = %s",
                    (override_id,),
                )
        # Cleanup the log row the test created.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                DELETE FROM canonical_match_log
                WHERE platform_market_id = %s AND action = 'override'
                """,
                (seeded_platform_market_id,),
            )
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_match_reviews_transition_to_approved_writes_log_with_manual_v1_join(
    db_pool: Any,
) -> None:
    """**LOAD-BEARING** per Holden Item 4 P3 scope-extension (build spec § 5c).

    INSERT review (pending) → transition_review(approved) via CRUD →
    SELECT log row with action='review_approve' → JOIN to
    match_algorithm → assert name='manual_v1' AND decided_by startswith
    'human:'.

    Bidirectional anchor for the manual_v1-on-human-decided-actions
    convention extended to the review_approve action.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()
    seeded_link_id = _seed_canonical_market_link(
        seeded_market_id, seeded_platform_market_id, algorithm_id
    )
    review_id: int | None = None

    try:
        review_id = create_review(link_id=seeded_link_id)
        transition_review(review_id=review_id, new_state="approved", reviewer="human:eric")

        with get_cursor() as cur:
            cur.execute(
                """
                SELECT cml.action, cml.decided_by, ma.name AS algorithm_name
                FROM canonical_match_log cml
                JOIN match_algorithm ma ON ma.id = cml.algorithm_id
                WHERE cml.link_id = %s AND cml.action = 'review_approve'
                ORDER BY cml.decided_at DESC
                LIMIT 1
                """,
                (seeded_link_id,),
            )
            log_row = cur.fetchone()
        assert log_row is not None, (
            "convention violated: no canonical_match_log row with "
            "action='review_approve' found for the approved review"
        )
        assert log_row["algorithm_name"] == "manual_v1", (
            f"manual_v1-on-human-decided-actions convention violated for "
            f"review_approve: expected algorithm name='manual_v1', got "
            f"{log_row['algorithm_name']!r}"
        )
        assert log_row["decided_by"].startswith("human:"), (
            f"human-only invariant violated at LOG read-back: "
            f"decided_by={log_row['decided_by']!r} should start with 'human:'"
        )
    finally:
        if review_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM canonical_match_reviews WHERE id = %s",
                    (review_id,),
                )
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                DELETE FROM canonical_match_log
                WHERE link_id = %s AND action IN ('review_approve', 'review_reject')
                """,
                (seeded_link_id,),
            )
        _cleanup_canonical_market_link(seeded_link_id)
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_match_reviews_transition_to_rejected_writes_log_with_manual_v1_join(
    db_pool: Any,
) -> None:
    """**LOAD-BEARING** per Holden Item 4 P3 scope-extension parallel.

    Parallel of the approved test for review_reject action.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()
    seeded_link_id = _seed_canonical_market_link(
        seeded_market_id, seeded_platform_market_id, algorithm_id
    )
    review_id: int | None = None

    try:
        review_id = create_review(link_id=seeded_link_id)
        transition_review(review_id=review_id, new_state="rejected", reviewer="human:eric")

        with get_cursor() as cur:
            cur.execute(
                """
                SELECT cml.action, cml.decided_by, ma.name AS algorithm_name
                FROM canonical_match_log cml
                JOIN match_algorithm ma ON ma.id = cml.algorithm_id
                WHERE cml.link_id = %s AND cml.action = 'review_reject'
                ORDER BY cml.decided_at DESC
                LIMIT 1
                """,
                (seeded_link_id,),
            )
            log_row = cur.fetchone()
        assert log_row is not None, (
            "convention violated: no canonical_match_log row with "
            "action='review_reject' found for the rejected review"
        )
        assert log_row["algorithm_name"] == "manual_v1", (
            f"manual_v1-on-human-decided-actions convention violated for "
            f"review_reject: expected algorithm name='manual_v1', got "
            f"{log_row['algorithm_name']!r}"
        )
        assert log_row["decided_by"].startswith("human:"), (
            f"human-only invariant violated at LOG read-back: "
            f"decided_by={log_row['decided_by']!r} should start with 'human:'"
        )
    finally:
        if review_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM canonical_match_reviews WHERE id = %s",
                    (review_id,),
                )
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                DELETE FROM canonical_match_log
                WHERE link_id = %s AND action IN ('review_approve', 'review_reject')
                """,
                (seeded_link_id,),
            )
        _cleanup_canonical_market_link(seeded_link_id)
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 7: Slot-0073 #1085 #12 deferral — get_match_log_for_link include_orphans
# round-trip integration test (lands in slot 0074 per inheritance note)
# =============================================================================


def test_canonical_match_log_post_link_delete_orphan_recovery_via_platform_market_id(
    db_pool: Any,
) -> None:
    """**LOAD-BEARING** per #1085 #12 deferral inheritance.

    Renamed from
    ``test_canonical_match_log_get_match_log_for_link_include_orphans_round_trip``
    per Ripley F9 P2 (#1095 close-out): the prior name overclaimed
    "include_orphans round trip" but this test exclusively exercises the
    orphan-recovery path via ``get_match_log_for_platform_market`` /
    direct-SQL on platform_market_id (the canonical query template from
    slot 0073's module docstring).  ``get_match_log_for_link`` with
    ``include_orphans=True`` returns 0 rows here BY DESIGN because the
    link row is deleted, breaking the attribution-tuple anchor.

    The companion test
    ``test_get_match_log_for_link_include_orphans_with_live_link_returns_them``
    below exercises the actual ``include_orphans=True`` path against a
    live link.

    INTEGRATION test (not unit); uses real DB:
        - create_review() (slot 0074) + transition_review('approved') →
          creates log row with action='review_approve' tied to link_id.
        - DELETE the link row → log rows survive with link_id=NULL via
          v2.42 sub-amendment B SET NULL.
        - get_match_log_for_link(link_id, include_orphans=True) returns
          0 rows by design (link row gone, attribution tuple lost).
        - SELECT directly by platform_market_id (the canonical query
          template) returns the orphan rows.

    Particularly relevant in slot 0074 because the override surface
    introduces nullable canonical_market_id (MUST_NOT_MATCH polarity)
    that exercises the orphan-lookup path's IS NOT DISTINCT FROM clause
    on canonical_market_id.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()
    seeded_link_id = _seed_canonical_market_link(
        seeded_market_id, seeded_platform_market_id, algorithm_id
    )
    review_id: int | None = None

    try:
        # Write a link-action log row directly to anchor the live link
        # history.  We don't capture the returned id — cleanup is by
        # platform_market_id in the finally block.
        append_match_log_row(
            link_id=seeded_link_id,
            platform_market_id=seeded_platform_market_id,
            canonical_market_id=seeded_market_id,
            action="link",
            confidence=None,
            algorithm_id=algorithm_id,
            features=None,
            prior_link_id=None,
            decided_by="system:test",
        )

        # Create + approve a review; transition writes a log row tied to link_id.
        review_id = create_review(link_id=seeded_link_id)
        transition_review(review_id=review_id, new_state="approved", reviewer="human:eric")

        # Pre-condition: include_orphans=False sees both link rows (link +
        # review_approve).
        live_rows = get_match_log_for_link(seeded_link_id, include_orphans=False)
        assert len(live_rows) == 2, (
            f"pre-condition: expected 2 live link-id-keyed log rows "
            f"(link + review_approve), got {len(live_rows)}"
        )

        # DELETE the link row — slot-0073's v2.42 sub-amendment B SET NULL
        # fires; reviews CASCADE; log rows survive with link_id NULL.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_market_links WHERE id = %s",
                (seeded_link_id,),
            )
        review_id = None  # cascaded

        # Post-condition: include_orphans=False misses the orphans.
        live_rows_after = get_match_log_for_link(seeded_link_id, include_orphans=False)
        assert len(live_rows_after) == 0, (
            f"post-condition include_orphans=False should return 0 rows "
            f"after link DELETE; got {len(live_rows_after)} (orphan rows "
            f"have link_id=NULL and don't match the strict equality query)"
        )

        # NOTE: include_orphans=True requires the link row to still exist
        # so its attribution tuple can anchor the orphan lookup.  The
        # docstring on get_match_log_for_link says: "include_orphans=True
        # requires the link row to still exist (so we can recover its
        # attribution tuple)."  After the DELETE above, the link row is
        # gone, so include_orphans=True cannot recover the orphans via
        # the link-id projection; it returns 0 rows.  This is the
        # canonical contract — orphan recovery via platform_market_id
        # is the alternative path documented in the Educational Note.
        orphan_rows = get_match_log_for_link(seeded_link_id, include_orphans=True)
        assert len(orphan_rows) == 0, (
            f"include_orphans=True after link DELETE returns 0 rows by "
            f"design (link attribution gone); recovery path is "
            f"get_match_log_for_platform_market.  Got {len(orphan_rows)}"
        )

        # The orphan-aware recovery path: query by platform_market_id.
        # This is the v2.42 sub-amendment B canonical query template
        # documented in slot 0073's module docstring.
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT id, link_id, platform_market_id, action
                FROM canonical_match_log
                WHERE platform_market_id = %s
                  AND action IN ('link', 'review_approve')
                ORDER BY decided_at DESC
                """,
                (seeded_platform_market_id,),
            )
            recovered = cur.fetchall()
        assert len(recovered) == 2, (
            f"orphan recovery via platform_market_id should return 2 rows "
            f"(link + review_approve, both with link_id=NULL post-DELETE); "
            f"got {len(recovered)}"
        )
        for row in recovered:
            assert row["link_id"] is None, (
                f"v2.42 sub-amendment B SET NULL contract violated: "
                f"row id={row['id']} should have link_id=NULL after link "
                f"DELETE; got {row['link_id']!r}"
            )
    finally:
        if review_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM canonical_match_reviews WHERE id = %s",
                    (review_id,),
                )
        # Defensive idempotent cleanup of the link row.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_market_links WHERE id = %s",
                (seeded_link_id,),
            )
        # Cleanup all log rows the test created.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                DELETE FROM canonical_match_log
                WHERE platform_market_id = %s
                """,
                (seeded_platform_market_id,),
            )
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_get_match_log_for_link_include_orphans_with_live_link_returns_them(
    db_pool: Any,
) -> None:
    """**LOAD-BEARING** per Ripley F9 P2 (#1095 close-out).

    Companion to ``test_canonical_match_log_post_link_delete_orphan_recovery
    _via_platform_market_id`` above which exercises the post-DELETE path.
    This test exercises the actual ``include_orphans=True`` mode against
    a LIVE link row — the path the docstring on ``get_match_log_for_link``
    promises (the link row's attribution tuple anchors the orphan
    lookup).

    Setup:
        1. Seed link L1 + write log row R1 (action='link') tied to L1.
        2. Write log row R2 directly with link_id=NULL but matching
           (platform_market_id, canonical_market_id) = L1's tuple — this
           simulates an orphan row whose original link was deleted before
           L1 was seeded (e.g., a re-link rebuild scenario where the
           historical orphan tuple persists).
        3. Call ``get_match_log_for_link(L1.id, include_orphans=True)`` —
           the live-branch returns R1; the UNION's orphan-branch joins
           on (platform_market_id, canonical_market_id) = L1's tuple
           AND link_id IS NULL → returns R2.
        4. Assert both R1 + R2 are present in the result.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()
    seeded_link_id = _seed_canonical_market_link(
        seeded_market_id, seeded_platform_market_id, algorithm_id
    )

    try:
        # R1: live-link log row.
        r1_id = append_match_log_row(
            link_id=seeded_link_id,
            platform_market_id=seeded_platform_market_id,
            canonical_market_id=seeded_market_id,
            action="link",
            confidence=None,
            algorithm_id=algorithm_id,
            features=None,
            prior_link_id=None,
            decided_by="system:test",
        )

        # R2: orphan-tuple log row (link_id=NULL, but attribution tuple
        # matches L1).  Direct INSERT since the public CRUD requires a
        # valid link_id; the orphan is the post-DELETE shape that
        # surfaces here pre-DELETE for the integration test.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_match_log (
                    link_id, platform_market_id, canonical_market_id,
                    action, confidence, algorithm_id, features,
                    prior_link_id, decided_by, note
                ) VALUES (
                    NULL, %s, %s, 'unlink', NULL, %s, NULL, NULL,
                    'system:test', 'pre-existing orphan tuple'
                )
                RETURNING id
                """,
                (seeded_platform_market_id, seeded_market_id, algorithm_id),
            )
            r2_id = int(cur.fetchone()["id"])

        # Pre-condition: include_orphans=False returns ONLY R1 (link_id-keyed).
        live_only = get_match_log_for_link(seeded_link_id, include_orphans=False)
        live_only_ids = {row["id"] for row in live_only}
        assert r1_id in live_only_ids, (
            f"include_orphans=False should return R1 (link_id-keyed live row); "
            f"got ids {live_only_ids!r}"
        )
        assert r2_id not in live_only_ids, (
            f"include_orphans=False MUST exclude R2 (orphan with link_id=NULL); "
            f"got ids {live_only_ids!r}"
        )

        # The actual include_orphans=True contract: live link → returns R1
        # via the link_id branch AND R2 via the UNION orphan-tuple branch.
        all_rows = get_match_log_for_link(seeded_link_id, include_orphans=True)
        all_ids = {row["id"] for row in all_rows}
        assert r1_id in all_ids, (
            f"include_orphans=True should return R1 (live link branch); got ids {all_ids!r}"
        )
        assert r2_id in all_ids, (
            f"include_orphans=True should return R2 via the UNION orphan-tuple "
            f"branch (link_id IS NULL + (platform_market_id, "
            f"canonical_market_id) matches the live link); got ids {all_ids!r}"
        )
    finally:
        # Clean up all log rows the test created.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                DELETE FROM canonical_match_log
                WHERE platform_market_id = %s
                """,
                (seeded_platform_market_id,),
            )
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_market_links WHERE id = %s",
                (seeded_link_id,),
            )
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 8: Indexes (#1085 #18 — DESC direction + partial WHERE assertions)
# =============================================================================


@pytest.mark.parametrize(
    ("index_name", "column", "is_partial", "is_desc"),
    [
        ("idx_canonical_match_reviews_link_id", "link_id", False, False),
        (
            "idx_canonical_match_reviews_review_state",
            "review_state",
            True,
            False,
        ),
        ("idx_canonical_match_reviews_reviewed_at", "reviewed_at", True, True),
    ],
)
def test_canonical_match_reviews_indexes_exist(
    db_pool: Any,
    index_name: str,
    column: str,
    is_partial: bool,
    is_desc: bool,
) -> None:
    """Each of the 3 reviews-table indexes exists on the prescribed column.

    #1085 #18 inheritance: index existence tests assert direction (DESC
    where applicable on reviewed_at) + partial WHERE clause where
    applicable.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexdef FROM pg_indexes
            WHERE tablename = 'canonical_match_reviews' AND indexname = %s
            """,
            (index_name,),
        )
        row = cur.fetchone()
    assert row is not None, (
        f"{index_name} missing post-0074 (Cohort 3 final-slot indexing strategy)"
    )
    indexdef = row["indexdef"]
    assert column in indexdef, f"{index_name} must reference column {column!r}; got: {indexdef}"
    if is_partial:
        assert "WHERE" in indexdef, (
            f"{index_name} must be partial (WHERE clause expected); got: {indexdef}"
        )
    if is_desc:
        assert "DESC" in indexdef, (
            f"{index_name} must be DESC-ordered (#1085 #18 — direction "
            f"asserted explicitly); got: {indexdef}"
        )
    assert "CREATE UNIQUE" not in indexdef, (
        f"index {index_name} must NOT be UNIQUE; got: {indexdef}"
    )


@pytest.mark.parametrize(
    ("index_name", "column", "is_partial", "is_desc"),
    [
        (
            "idx_canonical_match_overrides_canonical_market_id",
            "canonical_market_id",
            True,
            False,
        ),
        ("idx_canonical_match_overrides_polarity", "polarity", False, False),
        ("idx_canonical_match_overrides_created_at", "created_at", False, True),
    ],
)
def test_canonical_match_overrides_indexes_exist(
    db_pool: Any,
    index_name: str,
    column: str,
    is_partial: bool,
    is_desc: bool,
) -> None:
    """Each of the 3 overrides-table indexes exists on the prescribed column.

    Mirror-symmetric with test_canonical_match_reviews_indexes_exist.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexdef FROM pg_indexes
            WHERE tablename = 'canonical_match_overrides' AND indexname = %s
            """,
            (index_name,),
        )
        row = cur.fetchone()
    assert row is not None, (
        f"{index_name} missing post-0074 (Cohort 3 final-slot indexing strategy)"
    )
    indexdef = row["indexdef"]
    assert column in indexdef, f"{index_name} must reference column {column!r}; got: {indexdef}"
    if is_partial:
        assert "WHERE" in indexdef, (
            f"{index_name} must be partial (WHERE clause expected); got: {indexdef}"
        )
    if is_desc:
        assert "DESC" in indexdef, (
            f"{index_name} must be DESC-ordered (#1085 #18 — direction "
            f"asserted explicitly); got: {indexdef}"
        )
    assert "CREATE UNIQUE" not in indexdef, (
        f"index {index_name} must NOT be UNIQUE; got: {indexdef}"
    )
