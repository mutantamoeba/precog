"""Integration tests for migration 0073 — Cohort 3 canonical_match_log.

Verifies the POST-MIGRATION state of the ``canonical_match_log`` table
introduced by migration 0073 — Cohort 3 third slot, the append-only audit
ledger for the matching layer.  Per session-78 5-slot adjudication
(ADR-118 v2.41 amendment) + session-80 S82 design-stage P41 council
inheritance + session-81 PM build spec + Holden re-engagement memo
(``memory/build_spec_0073_pm_memo.md`` + ``memory/holden_reengagement_0073_memo.md``).

Test groups:
    - Column shape: per-column type / nullability / default / max-length
      with mirror-symmetric f-string assertion messages from day 1
      (#1085 finding #4 — slot 0073 inherits the lesson).
    - CHECK constraints: action 7-value vocab + confidence bound — both
      fire when violated.
    - Indexes: 4 indexes (decided_at DESC, platform_market_id, link_id
      partial, algorithm_id) all present.

    THREE LOAD-BEARING FK SURVIVAL TESTS (build spec § 6 binding):
        - link_id ON DELETE SET NULL (v2.42 sub-amendment B canonical
          test).
        - prior_link_id ON DELETE SET NULL (Holden P2 — symmetric
          survival semantics; absent test would let a future migration
          silently relax the clause).
        - canonical_market_id ON DELETE SET NULL (Holden P1 trap-prevention
          — ADR DDL was silent; would have repeated the v2.42 trap if
          unfilled).

    LOAD-BEARING L9 TEST:
        - platform_market_id NO FK — DELETE markets.id row referenced in
          log → log row survives intact (the v2.42 design intent verbatim).

Pattern 73 SSOT discipline test:
    - Imports ``ACTION_VALUES`` from constants.py and asserts each value
      is acceptable in the DDL CHECK.  Ensures the CRUD-layer constant
      and the DDL CHECK don't drift.

Issue: Epic #972 (Canonical Layer Foundation — Phase B.5), #1058,
    #1085 (slot-0073 polish-item inheritance)
ADR: ADR-118 v2.41 + v2.42 sub-amendment B
Build spec: ``memory/build_spec_0073_pm_memo.md``
Holden re-engagement: ``memory/holden_reengagement_0073_memo.md``

Markers:
    @pytest.mark.integration: real DB required.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import psycopg2
import psycopg2.errors
import pytest

from precog.database.connection import get_cursor
from precog.database.constants import ACTION_VALUES
from precog.database.crud_canonical_match_log import append_match_log_row
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
# Per-column shape spec (mirrors migration 0073 DDL verbatim).
#
# Each tuple: (column_name, data_type, is_nullable, default_substring_or_None,
#              max_char_length_or_None).
# Pattern 73 SSOT: the migration owns the column shape in code; this spec
# mirrors verbatim.  Drift here => test fails => alignment forced.
# Mirror-symmetric assertion messages per #1085 finding #4 (slot-0072
# review found asymmetry between market_links and event_links assertions;
# slot 0073 ships symmetric f-strings from day 1).
# =============================================================================

_MATCH_LOG_COLS: list[tuple[str, str, str, str | None, int | None]] = [
    ("id", "bigint", "NO", "nextval", None),
    ("link_id", "bigint", "YES", None, None),
    ("platform_market_id", "integer", "NO", None, None),
    ("canonical_market_id", "bigint", "YES", None, None),
    ("action", "character varying", "NO", None, 16),
    ("confidence", "numeric", "YES", None, None),
    ("algorithm_id", "bigint", "NO", None, None),
    ("features", "jsonb", "YES", None, None),
    ("prior_link_id", "bigint", "YES", None, None),
    ("decided_by", "character varying", "NO", None, 64),
    ("decided_at", "timestamp with time zone", "NO", "now()", None),
    ("note", "text", "YES", None, None),
    ("created_at", "timestamp with time zone", "NO", "now()", None),
]


# =============================================================================
# Seed helpers.
# =============================================================================


def _insert_log_row(
    *,
    link_id: int | None,
    platform_market_id: int,
    canonical_market_id: int | None,
    action: str = "link",
    confidence: Decimal | None = Decimal("0.987"),
    algorithm_id: int,
    features: str | None = None,
    prior_link_id: int | None = None,
    decided_by: str = "system:test",
    note: str | None = None,
) -> int:
    """Insert a canonical_match_log row directly via SQL (test convenience).

    Note: the production write path is
    ``crud_canonical_match_log.append_match_log_row()``; the integration
    tests use direct SQL to exercise the raw DDL contracts.
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO canonical_match_log (
                link_id, platform_market_id, canonical_market_id, action,
                confidence, algorithm_id, features, prior_link_id, decided_by, note
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s::jsonb, %s, %s, %s
            )
            RETURNING id
            """,
            (
                link_id,
                platform_market_id,
                canonical_market_id,
                action,
                confidence,
                algorithm_id,
                features,
                prior_link_id,
                decided_by,
                note,
            ),
        )
        return int(cur.fetchone()["id"])


# =============================================================================
# Group 1: canonical_match_log table column shape (#1085 finding #4 mirror-
# symmetric f-string assertion messages from day 1)
# =============================================================================


@pytest.mark.parametrize(
    ("col_name", "data_type", "is_nullable", "default_substr", "max_char_len"),
    _MATCH_LOG_COLS,
)
def test_canonical_match_log_column_shape(
    db_pool: Any,
    col_name: str,
    data_type: str,
    is_nullable: str,
    default_substr: str | None,
    max_char_len: int | None,
) -> None:
    """Each column on canonical_match_log has the migration-prescribed shape.

    #1085 finding #4 inheritance: assertion messages are detailed
    f-strings from day 1, mirror-symmetric across all checks.  This test
    is the canonical reference for "what does a canonical_match_log row
    column look like in the DB schema"; drift here forces alignment.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT data_type, is_nullable, column_default, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'canonical_match_log'
              AND column_name = %s
              AND table_schema = 'public'
            """,
            (col_name,),
        )
        row = cur.fetchone()
    assert row is not None, (
        f"canonical_match_log.{col_name} missing post-0073 — expected per migration DDL"
    )
    assert row["data_type"] == data_type, (
        f"canonical_match_log.{col_name} type mismatch: "
        f"expected {data_type!r}, got {row['data_type']!r}"
    )
    assert row["is_nullable"] == is_nullable, (
        f"canonical_match_log.{col_name} nullability mismatch: "
        f"expected {is_nullable!r}, got {row['is_nullable']!r}"
    )
    if default_substr is not None:
        actual_default = row["column_default"] or ""
        assert default_substr.lower() in actual_default.lower(), (
            f"canonical_match_log.{col_name} default missing {default_substr!r}; "
            f"got {actual_default!r}"
        )
    if max_char_len is not None:
        assert row["character_maximum_length"] == max_char_len, (
            f"canonical_match_log.{col_name} max_length mismatch: "
            f"expected {max_char_len}, got {row['character_maximum_length']}"
        )


# =============================================================================
# Group 2: CHECK constraints fire when violated
# =============================================================================


def test_canonical_match_log_action_check_fires(db_pool: Any) -> None:
    """INSERT with action='not_a_real_action' raises CheckViolation.

    Tuple form ``(ForeignKeyViolation, RestrictViolation, CheckViolation)``
    matches sibling test pattern from migrations 0057, 0063, 0072 — defensive
    breadth in case future PG versions or constraint shapes route the
    violation through an alternate class.  In practice this fires SQLSTATE
    23514 (CheckViolation).
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()

    try:
        with pytest.raises(
            (
                psycopg2.errors.ForeignKeyViolation,
                psycopg2.errors.RestrictViolation,
                psycopg2.errors.CheckViolation,
            )
        ):
            # Use a value <= VARCHAR(16) but NOT in ACTION_VALUES so the CHECK
            # fires rather than the column-length truncation error.
            _insert_log_row(
                link_id=None,
                platform_market_id=seeded_platform_market_id,
                canonical_market_id=seeded_market_id,
                action="bogus",  # 5 chars, not in ACTION_VALUES → CHECK fires
                algorithm_id=algorithm_id,
            )
    finally:
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_match_log_confidence_check_fires(db_pool: Any) -> None:
    """INSERT with confidence=1.5 raises CheckViolation."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()

    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            _insert_log_row(
                link_id=None,
                platform_market_id=seeded_platform_market_id,
                canonical_market_id=seeded_market_id,
                action="link",
                confidence=Decimal("1.5"),  # > 1 → CHECK fires
                algorithm_id=algorithm_id,
            )
    finally:
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_match_log_action_vocabulary_pattern_73_ssot(db_pool: Any) -> None:
    """Pattern 73 SSOT: every value in ACTION_VALUES is accepted by the DDL CHECK.

    Real-guard cross-layer assertion.  If the constants.py value-set and the
    DDL CHECK drift apart, this test fires.  This is the lockstep guarantee
    Pattern 73 SSOT provides — the import + the DDL CHECK are the two
    co-authoritative locations and must update together.
    """
    # Sentinel: the import is REAL-GUARD usage (#1085 finding #2).
    assert "review_approve" in ACTION_VALUES, (
        "ACTION_VALUES must include 'review_approve' per session-80 "
        "PM adjudication of Open Item B (UNIFIED SHAPE for audit ledger)"
    )

    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()

    inserted_log_ids: list[int] = []
    try:
        for canonical_action in ACTION_VALUES:
            log_id = _insert_log_row(
                link_id=None,
                platform_market_id=seeded_platform_market_id,
                canonical_market_id=seeded_market_id,
                action=canonical_action,
                algorithm_id=algorithm_id,
            )
            inserted_log_ids.append(log_id)
        # All 7 inserts succeeded — vocabulary lockstep verified.
        assert len(inserted_log_ids) == len(ACTION_VALUES), (
            f"Pattern 73 SSOT lockstep failure — expected "
            f"{len(ACTION_VALUES)} inserts, got {len(inserted_log_ids)}"
        )
    finally:
        with get_cursor(commit=True) as cur:
            for log_id in inserted_log_ids:
                cur.execute("DELETE FROM canonical_match_log WHERE id = %s", (log_id,))
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 2.5: Append-only via application discipline — honesty test
# =============================================================================


def test_canonical_match_log_raw_update_succeeds_today_trigger_deferred_to_slot_0090(
    db_pool: Any,
) -> None:
    """**HONESTY TEST per Ripley P1 sentinel finding (session 81).**

    The build spec (§ 2 design note 1, L10) declares append-only is enforced
    by application discipline (CRUD-module restriction), NOT by trigger.
    Trigger enforcement is deferred to slot 0090 after a 30-day soak window
    per Elrond E:90.  This means: **today, a raw SQL UPDATE or DELETE on
    canonical_match_log SUCCEEDS at the database level.**  Only the CRUD
    module's restricted ``append_match_log_row()`` API is the *sanctioned*
    write path; nothing about the schema itself prevents tampering.

    Without this test, a reader scanning the integration test suite would
    see "append-only" everywhere and reasonably assume the table is hard-
    protected.  The 30-day soak window before slot 0090 trigger ships
    would be invisible.  This test makes the discipline-gap **living-doc
    visible** — and provides a regression catch when slot 0090 ships:
    once the trigger is in place, this test must be **inverted** to
    expect a raise (and renamed to drop the "_succeeds_today" suffix).

    The test deliberately bypasses ``append_match_log_row()`` to demonstrate
    that the discipline gap exists.  Production code MUST NOT do this; this
    test is the documentation that the discipline is in fact a discipline,
    not a hard schema invariant.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()
    log_id: int | None = None

    try:
        # Append a baseline log row via the sanctioned API.
        log_id = append_match_log_row(
            link_id=None,
            platform_market_id=seeded_platform_market_id,
            canonical_market_id=seeded_market_id,
            action="link",
            confidence=Decimal("0.900"),
            algorithm_id=algorithm_id,
            features=None,
            prior_link_id=None,
            decided_by="system:test",
            note="baseline",
        )

        # Demonstrate UPDATE succeeds today — discipline gap is real.
        # When slot 0090 ships its append-only trigger, this UPDATE will
        # raise; this test must then be inverted (pytest.raises wrapper).
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE canonical_match_log SET note = %s WHERE id = %s",
                ("tampered-by-honesty-test", log_id),
            )

        # Verify the tamper landed: the discipline is via app code, not DB.
        with get_cursor() as cur:
            cur.execute("SELECT note FROM canonical_match_log WHERE id = %s", (log_id,))
            row = cur.fetchone()
        assert row is not None, "log row vanished — neither UPDATE nor DELETE expected here"
        assert row["note"] == "tampered-by-honesty-test", (
            "raw UPDATE should succeed today (trigger enforcement is slot 0090); "
            "if this assertion fires, the trigger has been retrofitted earlier "
            "than planned — invert this test to expect pytest.raises."
        )

        # Demonstrate DELETE succeeds today (parallel discipline-gap surface).
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM canonical_match_log WHERE id = %s", (log_id,))

        with get_cursor() as cur:
            cur.execute("SELECT id FROM canonical_match_log WHERE id = %s", (log_id,))
            row = cur.fetchone()
        assert row is None, (
            "raw DELETE should succeed today (trigger enforcement is slot 0090); "
            "if this assertion fires, the trigger has been retrofitted earlier "
            "than planned — invert this test to expect pytest.raises."
        )
        log_id = None  # already deleted; cleanup must skip
    finally:
        if log_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute("DELETE FROM canonical_match_log WHERE id = %s", (log_id,))
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 3: THREE LOAD-BEARING FK SURVIVAL TESTS (build spec § 6 binding)
# =============================================================================


def test_canonical_match_log_link_id_set_null_on_delete(db_pool: Any) -> None:
    """**LOAD-BEARING per v2.42 sub-amendment B + build spec § 6.**

    INSERT log row → DELETE link → verify log row's ``link_id`` is now
    NULL while other columns survive.  This is the canonical proof of
    v2.42 sub-amendment B (link_id ON DELETE SET NULL — audit history
    outlives link deletion).

    Failure mode this test prevents: a future migration silently
    relaxing the SET NULL clause to NO ACTION (or RESTRICT) would block
    link deletion in production while the audit log references existed —
    exact failure mode v2.42 was filed to close.

    #1085 finding #1 inheritance: log_id pre-initialized to None before
    try; cleanup guarded with `if log_id is not None`.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()
    seeded_link_id = _seed_canonical_market_link(
        seeded_market_id, seeded_platform_market_id, algorithm_id
    )

    log_id: int | None = None
    try:
        # Insert a log row that references the link.
        log_id = _insert_log_row(
            link_id=seeded_link_id,
            platform_market_id=seeded_platform_market_id,
            canonical_market_id=seeded_market_id,
            action="link",
            algorithm_id=algorithm_id,
            decided_by="system:test",
        )

        # Pre-conditions: log row's link_id is the seeded id; other attribution
        # columns are populated.
        with get_cursor() as cur:
            cur.execute(
                "SELECT link_id, platform_market_id, canonical_market_id, "
                "decided_by, algorithm_id FROM canonical_match_log WHERE id = %s",
                (log_id,),
            )
            pre_row = cur.fetchone()
        assert pre_row["link_id"] == seeded_link_id, (
            f"pre-condition: log row's link_id should be {seeded_link_id}, "
            f"got {pre_row['link_id']!r}"
        )

        # DELETE the link row — v2.42 sub-amendment B SET NULL must fire.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_market_links WHERE id = %s",
                (seeded_link_id,),
            )

        # Post-condition: log row survives, link_id is NULL, other attribution
        # preserved (the v2.42 design intent).
        with get_cursor() as cur:
            cur.execute(
                "SELECT link_id, platform_market_id, canonical_market_id, "
                "decided_by, algorithm_id FROM canonical_match_log WHERE id = %s",
                (log_id,),
            )
            post_row = cur.fetchone()
        assert post_row is not None, (
            "log row deleted by link DELETE — v2.42 SET NULL contract violated; "
            f"expected SET NULL semantic, got cascading delete on log_id={log_id}"
        )
        assert post_row["link_id"] is None, (
            f"link_id should be NULL after link DELETE (v2.42 sub-amendment B); "
            f"got {post_row['link_id']!r}"
        )
        assert post_row["platform_market_id"] == seeded_platform_market_id
        assert post_row["canonical_market_id"] == seeded_market_id
        assert post_row["decided_by"] == "system:test"
        assert post_row["algorithm_id"] == algorithm_id
    finally:
        if log_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute("DELETE FROM canonical_match_log WHERE id = %s", (log_id,))
        # Defensive: if DELETE in the try-block didn't run (test failed before
        # it), clean up the link too.  Idempotent via WHERE id =.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_market_links WHERE id = %s",
                (seeded_link_id,),
            )
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_match_log_prior_link_id_set_null_on_delete(db_pool: Any) -> None:
    """**LOAD-BEARING per Holden P2 + build spec § 6.**

    Symmetric to ``test_canonical_match_log_link_id_set_null_on_delete``
    on the prior_link_id column.  Both columns share v2.42 sub-amendment
    B's audit-survival semantics by parallel application of the same
    rule (Holden P3 deliberate spec-strengthening).

    INSERT log row with prior_link_id pointing to a link → DELETE that
    link → verify log row's prior_link_id is now NULL while other
    columns survive.

    Failure mode this test prevents: a future migration silently
    relaxing prior_link_id's ON DELETE clause (or removing the FK
    entirely) would break the relink/unlink predecessor-traceability
    invariant.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id_a = _seed_canonical_market(seeded_event_id, f"{suffix}-a")
    seeded_market_id_b = _seed_canonical_market(seeded_event_id, f"{suffix}-b")
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()
    # The "prior" link — will be deleted in this test.
    seeded_prior_link_id = _seed_canonical_market_link(
        seeded_market_id_a, seeded_platform_market_id, algorithm_id
    )

    # Retire the prior link so we can seed a new active link without an
    # EXCLUDE violation on platform_market_id.
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            UPDATE canonical_market_links
            SET link_state = 'retired', retired_at = now()
            WHERE id = %s
            """,
            (seeded_prior_link_id,),
        )
    # The "current" link — survives the prior link's deletion.
    seeded_current_link_id = _seed_canonical_market_link(
        seeded_market_id_b, seeded_platform_market_id, algorithm_id
    )

    log_id: int | None = None
    try:
        # Log row records a relink: current link, prior link, action='relink'.
        log_id = _insert_log_row(
            link_id=seeded_current_link_id,
            platform_market_id=seeded_platform_market_id,
            canonical_market_id=seeded_market_id_b,
            action="relink",
            algorithm_id=algorithm_id,
            prior_link_id=seeded_prior_link_id,
            decided_by="system:test",
        )

        # DELETE the prior link — prior_link_id ON DELETE SET NULL must fire.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_market_links WHERE id = %s",
                (seeded_prior_link_id,),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT link_id, prior_link_id, platform_market_id, "
                "canonical_market_id, decided_by, algorithm_id "
                "FROM canonical_match_log WHERE id = %s",
                (log_id,),
            )
            post_row = cur.fetchone()
        assert post_row is not None, (
            "log row deleted by prior link DELETE — prior_link_id SET NULL "
            "contract violated; expected SET NULL semantic on prior_link_id"
        )
        assert post_row["prior_link_id"] is None, (
            f"prior_link_id should be NULL after prior link DELETE "
            f"(Holden P2 / v2.42 sub-amendment B parallel application); "
            f"got {post_row['prior_link_id']!r}"
        )
        # The current link_id should NOT have been touched.
        assert post_row["link_id"] == seeded_current_link_id, (
            f"link_id should be unchanged after prior link DELETE; "
            f"expected {seeded_current_link_id}, got {post_row['link_id']!r}"
        )
        assert post_row["platform_market_id"] == seeded_platform_market_id
        assert post_row["canonical_market_id"] == seeded_market_id_b
    finally:
        if log_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute("DELETE FROM canonical_match_log WHERE id = %s", (log_id,))
        _cleanup_canonical_market_link(seeded_current_link_id)
        # prior link already deleted in the test body; defensive idempotent cleanup.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_market_links WHERE id = %s",
                (seeded_prior_link_id,),
            )
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id_a)
        _cleanup_canonical_market(seeded_market_id_b)
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_match_log_canonical_market_id_set_null_on_delete(db_pool: Any) -> None:
    """**LOAD-BEARING per Holden P1 + build spec § 6.**

    Holden re-engagement P1 trap-prevention test.  ADR DDL was silent on
    canonical_market_id's ON DELETE clause; PostgreSQL silent-NO-ACTION
    default would have repeated the v2.42 sub-amendment B trap.  Slot
    0073 explicitly chose ON DELETE SET NULL; this test is the contract
    proof that the choice is enforced in the DDL.

    INSERT log row → DELETE canonical_markets row → verify log row's
    canonical_market_id is now NULL while attribution survives via
    (platform_market_id, decided_at, decided_by, algorithm_id).

    Note: canonical_markets uses RESTRICT-style policies in production
    against link tables (slot 0072), but slot 0073's canonical_match_log
    intentionally uses SET NULL so that the audit ledger outlives
    canonical-row deletion.  This test exercises that path by inserting
    a log row WITHOUT a corresponding link-table row that would block
    canonical_markets DELETE via RESTRICT.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()

    log_id: int | None = None
    try:
        # Insert a log row that references the canonical market.  We
        # intentionally do NOT seed a canonical_market_links row here —
        # canonical_markets has ON DELETE RESTRICT against link tables (slot
        # 0072 L3 polarity), so seeding a link would block the
        # canonical_markets DELETE we want to exercise.  The log row's
        # canonical_market_id alone is what we're testing.
        log_id = _insert_log_row(
            link_id=None,
            platform_market_id=seeded_platform_market_id,
            canonical_market_id=seeded_market_id,
            action="override",  # human override — link_id may be NULL
            confidence=None,  # human overrides have no algorithmic confidence
            algorithm_id=algorithm_id,  # manual_v1 placeholder
            decided_by="human:test",
        )

        # DELETE canonical_markets — canonical_market_id SET NULL must fire.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_markets WHERE id = %s",
                (seeded_market_id,),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT canonical_market_id, platform_market_id, "
                "decided_at, decided_by, algorithm_id, action "
                "FROM canonical_match_log WHERE id = %s",
                (log_id,),
            )
            post_row = cur.fetchone()
        assert post_row is not None, (
            "log row deleted by canonical_markets DELETE — Holden P1 "
            "trap-prevention contract violated; expected SET NULL semantic "
            "on canonical_market_id"
        )
        assert post_row["canonical_market_id"] is None, (
            f"canonical_market_id should be NULL after canonical_markets DELETE "
            f"(Holden P1 trap-prevention); got {post_row['canonical_market_id']!r}"
        )
        # Attribution survives via the other columns.
        assert post_row["platform_market_id"] == seeded_platform_market_id
        assert post_row["decided_by"] == "human:test"
        assert post_row["algorithm_id"] == algorithm_id
        assert post_row["action"] == "override"
    finally:
        if log_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute("DELETE FROM canonical_match_log WHERE id = %s", (log_id,))
        _cleanup_platform_market(seeded_platform_market_id)
        # canonical_markets row already DELETEd in test body unless an
        # earlier assertion failed; idempotent cleanup is safe.
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 4: LOAD-BEARING L9 TEST — platform_market_id NO FK
# =============================================================================


def test_canonical_match_log_platform_market_id_no_fk(db_pool: Any) -> None:
    """**LOAD-BEARING per L9 + build spec § 2 design notes.**

    DELETE markets row referenced in log → log row survives intact.

    L9 framing (migration docstring): "the log is the truth of who
    decided what; the platform row is a lookup target that may
    legitimately disappear."  This test is the contract proof that the
    deliberate-no-FK design intent is enforced (or rather, that no FK
    silently exists to violate it).

    Failure mode this test prevents: a future migration silently adding
    an FK on platform_market_id would block (or CASCADE) on platform-row
    deletion — undoing the L9 audit-ledger-survives-platform-deletion
    contract.

    Sister test to slot 0072's CASCADE test on canonical_market_links —
    different polarity (NO FK here vs CASCADE there) but the same
    "verify the polarity is what we intended" shape.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()

    log_id: int | None = None
    try:
        # Insert a log row referencing the platform_market by id (NO FK at
        # the DB layer; the integer is just an integer).
        log_id = _insert_log_row(
            link_id=None,
            platform_market_id=seeded_platform_market_id,
            canonical_market_id=seeded_market_id,
            action="link",
            algorithm_id=algorithm_id,
            decided_by="system:test",
        )

        # DELETE the platform market — no FK exists, so delete succeeds
        # AND the log row's platform_market_id stays as the (now-orphan)
        # integer value.  The L9 design intent: log outlives platform row.
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM markets WHERE id = %s", (seeded_platform_market_id,))

        with get_cursor() as cur:
            cur.execute(
                "SELECT platform_market_id, canonical_market_id, decided_by, "
                "algorithm_id, action FROM canonical_match_log WHERE id = %s",
                (log_id,),
            )
            post_row = cur.fetchone()
        assert post_row is not None, (
            "L9 contract violated — log row should survive platform_market "
            "DELETE since no FK exists; got NULL row"
        )
        # platform_market_id keeps the orphan integer value (NOT NULL!).
        assert post_row["platform_market_id"] == seeded_platform_market_id, (
            f"L9 audit-survival: platform_market_id should retain orphan int "
            f"value {seeded_platform_market_id} (NOT go to NULL), got "
            f"{post_row['platform_market_id']!r}"
        )
        assert post_row["canonical_market_id"] == seeded_market_id
        assert post_row["decided_by"] == "system:test"
        assert post_row["action"] == "link"
    finally:
        if log_id is not None:
            with get_cursor(commit=True) as cur:
                cur.execute("DELETE FROM canonical_match_log WHERE id = %s", (log_id,))
        # platform market already gone via test body's DELETE — no cleanup.
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 5: Indexes
# =============================================================================


@pytest.mark.parametrize(
    ("index_name", "column", "is_partial"),
    [
        ("idx_canonical_match_log_decided_at", "decided_at", False),
        ("idx_canonical_match_log_platform_market_id", "platform_market_id", False),
        ("idx_canonical_match_log_link_id", "link_id", True),
        ("idx_canonical_match_log_algorithm_id", "algorithm_id", False),
    ],
)
def test_canonical_match_log_indexes_exist(
    db_pool: Any, index_name: str, column: str, is_partial: bool
) -> None:
    """Each of the 4 indexes exists on the prescribed column.

    Holden slot-0073 indexing strategy (4 indexes total): decided_at DESC
    (operator audit hot path), platform_market_id (L9 query target),
    link_id partial (small-footprint lookup), algorithm_id (Miles
    operator-alert-query catalog).
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexdef FROM pg_indexes
            WHERE tablename = 'canonical_match_log' AND indexname = %s
            """,
            (index_name,),
        )
        row = cur.fetchone()
    assert row is not None, f"{index_name} missing post-0073 (Holden indexing strategy contract)"
    indexdef = row["indexdef"]
    assert column in indexdef, f"{index_name} must reference column {column!r}; got: {indexdef}"
    if is_partial:
        assert "WHERE" in indexdef, (
            f"{index_name} must be partial (WHERE clause expected for "
            f"link_id partial index); got: {indexdef}"
        )
    # FK-target indexes are not unique by themselves.
    assert "CREATE UNIQUE" not in indexdef, (
        f"index {index_name} must NOT be UNIQUE; got: {indexdef}"
    )
