"""Integration tests for migration 0079 -- Cohort 4 canonical_event_phase_log.

Verifies the POST-MIGRATION state of the ``canonical_event_phase_log``
audit ledger introduced by Migration 0079 -- Cohort 4 second slot, the
event-phase audit table mirroring slot 0073's match-log shape.  Per
ADR-118 V2.40 Item 3 + V2.43 Item 2 + session 87 PM build spec at
``memory/build_spec_0079_pm_memo.md`` + session 87 S82 SKIP verdict at
``memory/s82_slot_0079_skip_memo.md``.

Test groups:
    - Column shape: per-column type / nullability / default / max-length
      with mirror-symmetric f-string assertion messages (slot 0073
      #1085 finding #4 inheritance).
    - CHECK constraints: new_phase / previous_phase 8-value vocab fires.
    - Indexes: 3 indexes (transition_at DESC, canonical_event_id,
      composite event_transition) all present.
    - FK polarity: canonical_event_id ON DELETE CASCADE.
    - Trigger function exists + has correct shape.
    - BEHAVIORAL trigger tests (build spec § 5b binding):
        * INSERT canonical_events -> phase_log row auto-created with
          previous_phase=NULL, new_phase=lifecycle_phase, changed_by=
          'system:trigger'.
        * UPDATE lifecycle_phase -> phase_log row with previous + new
          + 'system:trigger'.
        * UPDATE non-lifecycle column -> NO phase_log row created.
        * UPDATE with same lifecycle_phase value -> NO phase_log row
          (IS DISTINCT FROM correctness).
        * CASCADE DELETE on canonical_events removes phase_log rows.
    - Manual append_phase_transition() integration: row inserted with
      operator-supplied changed_by + note.
    - Manual append with invalid new_phase: CheckViolation surfaces
      from PG (defense in depth -- the CRUD layer ValueError validation
      should fire first, but if a future refactor bypasses it, the DDL
      CHECK is the safety net).

Pattern 73 SSOT discipline test:
    - Imports ``CANONICAL_EVENT_LIFECYCLE_PHASES`` from constants.py
      and asserts each value is acceptable in BOTH new_phase and
      previous_phase CHECKs.  Ensures the CRUD-layer constant and the
      DDL CHECKs don't drift.

Issue: Epic #972 (Canonical Layer Foundation -- Phase B.5)
ADR: ADR-118 V2.40 Item 3 + V2.43 Item 2
Build spec: ``memory/build_spec_0079_pm_memo.md``
S82 verdict: ``memory/s82_slot_0079_skip_memo.md``

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
from precog.database.constants import CANONICAL_EVENT_LIFECYCLE_PHASES
from precog.database.crud_canonical_event_phase_log import (
    append_phase_transition,
    get_phase_history_for_event,
)
from tests.integration.database._canonical_event_helpers import (
    _cleanup_canonical_event,
    _seed_canonical_event,
)

pytestmark = [pytest.mark.integration]


# =============================================================================
# Per-column shape spec (mirrors migration 0079 DDL verbatim).
#
# Each tuple: (column_name, data_type, is_nullable, default_substring_or_None,
#              max_char_length_or_None).
# Pattern 73 SSOT: the migration owns the column shape in code; this spec
# mirrors verbatim.  Drift here => test fails => alignment forced.
# Mirror-symmetric assertion messages per slot 0073 #1085 finding #4.
# =============================================================================

_PHASE_LOG_COLS: list[tuple[str, str, str, str | None, int | None]] = [
    ("id", "bigint", "NO", "nextval", None),
    ("canonical_event_id", "bigint", "NO", None, None),
    ("previous_phase", "character varying", "YES", None, 32),
    ("new_phase", "character varying", "NO", None, 32),
    ("transition_at", "timestamp with time zone", "NO", "now()", None),
    ("changed_by", "character varying", "NO", None, 64),
    ("note", "text", "YES", None, None),
    ("created_at", "timestamp with time zone", "NO", "now()", None),
]


# =============================================================================
# Group 1: canonical_event_phase_log table column shape
# =============================================================================


@pytest.mark.parametrize(
    ("col_name", "data_type", "is_nullable", "default_substr", "max_char_len"),
    _PHASE_LOG_COLS,
)
def test_canonical_event_phase_log_column_shape(
    db_pool: Any,
    col_name: str,
    data_type: str,
    is_nullable: str,
    default_substr: str | None,
    max_char_len: int | None,
) -> None:
    """Each column on canonical_event_phase_log has the migration-prescribed shape.

    Slot 0073 #1085 finding #4 inheritance: assertion messages are
    detailed f-strings, mirror-symmetric across all checks.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT data_type, is_nullable, column_default, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'canonical_event_phase_log'
              AND column_name = %s
              AND table_schema = 'public'
            """,
            (col_name,),
        )
        row = cur.fetchone()
    assert row is not None, (
        f"canonical_event_phase_log.{col_name} missing post-0079 -- expected per migration DDL"
    )
    assert row["data_type"] == data_type, (
        f"canonical_event_phase_log.{col_name} type mismatch: "
        f"expected {data_type!r}, got {row['data_type']!r}"
    )
    assert row["is_nullable"] == is_nullable, (
        f"canonical_event_phase_log.{col_name} nullability mismatch: "
        f"expected {is_nullable!r}, got {row['is_nullable']!r}"
    )
    if default_substr is not None:
        actual_default = row["column_default"] or ""
        assert default_substr.lower() in actual_default.lower(), (
            f"canonical_event_phase_log.{col_name} default missing {default_substr!r}; "
            f"got {actual_default!r}"
        )
    if max_char_len is not None:
        assert row["character_maximum_length"] == max_char_len, (
            f"canonical_event_phase_log.{col_name} max_length mismatch: "
            f"expected {max_char_len}, got {row['character_maximum_length']}"
        )


# =============================================================================
# Group 2: CHECK constraints fire when violated
# =============================================================================


def test_canonical_event_phase_log_new_phase_check_fires(db_pool: Any) -> None:
    """INSERT with new_phase='not_a_real_phase' raises CheckViolation."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)

    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_event_phase_log (
                        canonical_event_id, previous_phase, new_phase, changed_by
                    ) VALUES (%s, NULL, %s, %s)
                    """,
                    (seeded_event_id, "bad_phase", "system:test"),
                )
    finally:
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_event_phase_log_previous_phase_check_fires(db_pool: Any) -> None:
    """INSERT with non-NULL previous_phase='not_a_real_phase' raises CheckViolation."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)

    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_event_phase_log (
                        canonical_event_id, previous_phase, new_phase, changed_by
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    (seeded_event_id, "bad_phase", "live", "system:test"),
                )
    finally:
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_event_phase_log_previous_phase_null_accepted(db_pool: Any) -> None:
    """previous_phase=NULL is accepted (first-transition case)."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)

    # Note: the trigger has already inserted an INSERT-path row for this
    # event; so we just verify a manual NULL previous_phase additional row
    # also lands without CheckViolation.
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_event_phase_log (
                    canonical_event_id, previous_phase, new_phase, changed_by
                ) VALUES (%s, NULL, %s, %s)
                RETURNING id
                """,
                (seeded_event_id, "proposed", "system:test"),
            )
            assert cur.fetchone()["id"] is not None
    finally:
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_event_phase_log_new_phase_vocabulary_pattern_73_ssot(
    db_pool: Any,
) -> None:
    """Pattern 73 SSOT: every value in CANONICAL_EVENT_LIFECYCLE_PHASES accepted by both CHECKs.

    Real-guard cross-layer assertion.  If the constants.py value-set and
    the DDL CHECKs drift apart, this test fires.  Three-way SSOT parity
    (constant + Migration 0070 CHECK + Migration 0079 CHECKs) is verified
    in test_lifecycle_phase_vocabulary_ssot.py; this test exercises the
    runtime acceptance of every value via INSERT.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)

    try:
        for phase in CANONICAL_EVENT_LIFECYCLE_PHASES:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_event_phase_log (
                        canonical_event_id, previous_phase, new_phase, changed_by
                    ) VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (seeded_event_id, phase, phase, "system:test"),
                )
                row = cur.fetchone()
                assert row is not None, (
                    f"INSERT with new_phase={phase!r} + previous_phase={phase!r} "
                    f"must return a row (Pattern 73 SSOT lockstep)"
                )
                assert row["id"] is not None, (
                    f"INSERT with new_phase={phase!r} + previous_phase={phase!r} "
                    f"must populate id (Pattern 73 SSOT lockstep)"
                )
    finally:
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 3: indexes present
# =============================================================================


@pytest.mark.parametrize(
    "index_name",
    [
        "idx_canonical_event_phase_log_transition_at",
        "idx_canonical_event_phase_log_canonical_event_id",
        "idx_canonical_event_phase_log_event_transition",
    ],
)
def test_canonical_event_phase_log_index_present(db_pool: Any, index_name: str) -> None:
    """Each declared index exists post-0079."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexdef FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'canonical_event_phase_log'
              AND indexname = %s
            """,
            (index_name,),
        )
        row = cur.fetchone()
    assert row is not None, f"Index {index_name!r} must exist post-Migration-0079"
    assert "canonical_event_phase_log" in row["indexdef"], (
        f"Index {index_name!r} indexdef must reference the canonical_event_phase_log table; "
        f"got: {row['indexdef']!r}"
    )


def test_composite_index_orders_transition_at_desc(db_pool: Any) -> None:
    """Composite index has DESC ordering on transition_at (not ASC).

    Operator-runbook query "phase history for event X newest-first" uses
    this index; DESC-on-disk avoids a server-side reverse scan.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexdef FROM pg_indexes
            WHERE indexname = 'idx_canonical_event_phase_log_event_transition'
              AND schemaname = 'public'
            """,
        )
        row = cur.fetchone()
    assert row is not None
    assert "transition_at DESC" in row["indexdef"], (
        f"Composite index must declare transition_at DESC; got: {row['indexdef']!r}"
    )


# =============================================================================
# Group 4: trigger function + trigger exist
# =============================================================================


def test_log_phase_transition_function_exists(db_pool: Any) -> None:
    """``log_canonical_event_phase_transition()`` exists post-0079."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_functiondef(p.oid) AS def
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE p.proname = 'log_canonical_event_phase_transition'
              AND n.nspname = 'public'
            """
        )
        row = cur.fetchone()
    assert row is not None, "log_canonical_event_phase_transition() must exist post-Migration-0079"
    function_def = row["def"]
    # Body discipline: uses IS DISTINCT FROM for NULL-safety.
    assert "IS DISTINCT FROM" in function_def, (
        f"Function body must use IS DISTINCT FROM (NULL-safe phase comparison); "
        f"got: {function_def!r}"
    )
    # Body discipline: emits 'system:trigger' as changed_by.
    assert "system:trigger" in function_def, (
        f"Function body must emit changed_by='system:trigger' "
        f"(DECIDED_BY_PREFIXES system: prefix); got: {function_def!r}"
    )


def test_log_phase_transition_trigger_exists(db_pool: Any) -> None:
    """``trg_canonical_events_log_phase_transition`` exists on canonical_events."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_triggerdef(t.oid) AS def
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            WHERE c.relname = 'canonical_events'
              AND t.tgname = 'trg_canonical_events_log_phase_transition'
              AND NOT t.tgisinternal
            """,
        )
        row = cur.fetchone()
    assert row is not None, (
        "trg_canonical_events_log_phase_transition must exist on canonical_events"
    )
    trigger_def = row["def"]
    # Trigger fires AFTER (not BEFORE) -- audit-row writes after the canonical_events change.
    assert "AFTER" in trigger_def.upper(), (
        f"Trigger must fire AFTER (not BEFORE); got: {trigger_def}"
    )
    # Trigger fires on INSERT and UPDATE OF lifecycle_phase only (not on every UPDATE).
    assert "INSERT" in trigger_def.upper(), (
        f"Trigger must include INSERT firing scope; got: {trigger_def}"
    )
    assert "lifecycle_phase" in trigger_def, (
        f"Trigger UPDATE clause must restrict to OF lifecycle_phase; got: {trigger_def}"
    )


# =============================================================================
# Group 5: BEHAVIORAL trigger tests (build spec § 5b binding)
# =============================================================================


def test_trigger_fires_on_canonical_events_insert(db_pool: Any) -> None:
    """INSERT canonical_events -> phase_log row auto-created.

    previous_phase=NULL, new_phase=lifecycle_phase, changed_by='system:trigger'.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)

    try:
        # The seed helper INSERTs with lifecycle_phase='proposed'; the trigger
        # should have created exactly one phase_log row for that event.
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT canonical_event_id, previous_phase, new_phase,
                       changed_by, note
                FROM canonical_event_phase_log
                WHERE canonical_event_id = %s
                ORDER BY transition_at DESC, id DESC
                """,
                (seeded_event_id,),
            )
            rows = cur.fetchall()

        # Exactly one row created by the INSERT trigger path.
        assert len(rows) == 1, (
            f"INSERT trigger must create exactly 1 phase_log row; got {len(rows)}"
        )
        row = rows[0]
        assert row["canonical_event_id"] == seeded_event_id
        assert row["previous_phase"] is None, (
            f"INSERT-path row must have previous_phase=NULL; got {row['previous_phase']!r}"
        )
        assert row["new_phase"] == "proposed", (
            f"INSERT-path row must mirror seed lifecycle_phase='proposed'; got {row['new_phase']!r}"
        )
        assert row["changed_by"] == "system:trigger", (
            f"Auto-populated row must use changed_by='system:trigger'; got {row['changed_by']!r}"
        )
        assert "INSERT" in (row["note"] or ""), (
            f"INSERT-path note must reference INSERT; got {row['note']!r}"
        )
    finally:
        _cleanup_canonical_event(seeded_event_id)


def test_trigger_fires_on_canonical_events_lifecycle_phase_update(db_pool: Any) -> None:
    """UPDATE canonical_events SET lifecycle_phase = 'live' -> phase_log row added.

    Includes previous_phase=existing, new_phase=updated, changed_by='system:trigger'.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)

    try:
        # Seed inserts at lifecycle_phase='proposed' (1 phase_log row from trigger).
        # Now UPDATE to 'listed' (should add 1 more row).
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                UPDATE canonical_events
                SET lifecycle_phase = 'listed'
                WHERE id = %s
                """,
                (seeded_event_id,),
            )

        with get_cursor() as cur:
            cur.execute(
                """
                SELECT previous_phase, new_phase, changed_by
                FROM canonical_event_phase_log
                WHERE canonical_event_id = %s
                ORDER BY transition_at ASC, id ASC
                """,
                (seeded_event_id,),
            )
            rows = cur.fetchall()

        # 2 rows: one INSERT-path (NULL -> proposed), one UPDATE-path (proposed -> listed).
        assert len(rows) == 2, f"INSERT + UPDATE must produce 2 phase_log rows; got {len(rows)}"

        # First row is from INSERT path.
        assert rows[0]["previous_phase"] is None
        assert rows[0]["new_phase"] == "proposed"
        assert rows[0]["changed_by"] == "system:trigger"

        # Second row is from UPDATE path.
        assert rows[1]["previous_phase"] == "proposed"
        assert rows[1]["new_phase"] == "listed"
        assert rows[1]["changed_by"] == "system:trigger"
    finally:
        _cleanup_canonical_event(seeded_event_id)


def test_trigger_does_not_fire_on_non_lifecycle_phase_update(db_pool: Any) -> None:
    """UPDATE on a non-lifecycle_phase column must NOT create a phase_log row.

    Trigger declaration has UPDATE OF lifecycle_phase scope -- routine UPDATEs
    that touch other columns (title, updated_at) do NOT fire this trigger.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)

    try:
        # Count rows after INSERT (should be 1 from INSERT-trigger path).
        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM canonical_event_phase_log WHERE canonical_event_id = %s",
                (seeded_event_id,),
            )
            before_count = cur.fetchone()["n"]
        assert before_count == 1

        # UPDATE non-lifecycle_phase column.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE canonical_events SET title = %s WHERE id = %s",
                (f"Updated title ({suffix})", seeded_event_id),
            )

        # Count again -- should still be 1 (no new row).
        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM canonical_event_phase_log WHERE canonical_event_id = %s",
                (seeded_event_id,),
            )
            after_count = cur.fetchone()["n"]
        assert after_count == 1, (
            f"UPDATE on non-lifecycle_phase column must NOT create a new "
            f"phase_log row; before={before_count}, after={after_count}"
        )
    finally:
        _cleanup_canonical_event(seeded_event_id)


def test_trigger_does_not_fire_on_same_value_lifecycle_phase_update(db_pool: Any) -> None:
    """UPDATE lifecycle_phase to the SAME value must NOT create a phase_log row.

    The trigger function uses ``IS DISTINCT FROM`` so a no-op UPDATE
    (same lifecycle_phase value) is correctly skipped.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)

    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM canonical_event_phase_log WHERE canonical_event_id = %s",
                (seeded_event_id,),
            )
            before_count = cur.fetchone()["n"]
        assert before_count == 1

        # UPDATE lifecycle_phase to the SAME value.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                UPDATE canonical_events
                SET lifecycle_phase = 'proposed'
                WHERE id = %s
                """,
                (seeded_event_id,),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM canonical_event_phase_log WHERE canonical_event_id = %s",
                (seeded_event_id,),
            )
            after_count = cur.fetchone()["n"]
        assert after_count == 1, (
            f"UPDATE lifecycle_phase to same value must NOT create a new "
            f"phase_log row (IS DISTINCT FROM correctness); "
            f"before={before_count}, after={after_count}"
        )
    finally:
        _cleanup_canonical_event(seeded_event_id)


def test_cascade_delete_removes_phase_log_rows(db_pool: Any) -> None:
    """DELETE canonical_events -> CASCADE delete on canonical_event_phase_log.

    FK polarity: canonical_event_id ON DELETE CASCADE.  Audit log dies
    with the parent event (no parallel attribution tuple to anchor
    orphans, unlike slot 0073's match-log SET NULL semantics).
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)

    # Add 2 manual rows on top of the INSERT-trigger row (3 total).
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO canonical_event_phase_log
                (canonical_event_id, previous_phase, new_phase, changed_by)
            VALUES
                (%s, %s, %s, %s),
                (%s, %s, %s, %s)
            """,
            (
                seeded_event_id,
                "proposed",
                "listed",
                "human:eric",
                seeded_event_id,
                "listed",
                "live",
                "human:eric",
            ),
        )

    with get_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM canonical_event_phase_log WHERE canonical_event_id = %s",
            (seeded_event_id,),
        )
        before_count = cur.fetchone()["n"]
    assert before_count == 3, f"Pre-DELETE row count must be 3; got {before_count}"

    # DELETE canonical_events -> phase_log rows should CASCADE-delete.
    _cleanup_canonical_event(seeded_event_id)

    with get_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM canonical_event_phase_log WHERE canonical_event_id = %s",
            (seeded_event_id,),
        )
        after_count = cur.fetchone()["n"]
    assert after_count == 0, (
        f"CASCADE delete must remove all phase_log rows; before={before_count}, after={after_count}"
    )


# =============================================================================
# Group 6: FK polarity verification
# =============================================================================


def test_canonical_event_id_fk_on_delete_cascade(db_pool: Any) -> None:
    """canonical_event_phase_log.canonical_event_id has ON DELETE CASCADE polarity.

    DDL-level assertion: the FK definition includes the CASCADE clause.
    Behavioral CASCADE delete is exercised by
    test_cascade_delete_removes_phase_log_rows above; this test asserts
    the DDL polarity directly via pg_constraint inspection.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(con.oid) AS def
            FROM pg_constraint con
            JOIN pg_class cls ON cls.oid = con.conrelid
            WHERE cls.relname = 'canonical_event_phase_log'
              AND con.contype = 'f'
              AND con.conname LIKE '%canonical_event_id%'
            """
        )
        row = cur.fetchone()
    assert row is not None, "canonical_event_id FK must be defined"
    constraint_def = row["def"]
    assert "ON DELETE CASCADE" in constraint_def, (
        f"canonical_event_id FK must have ON DELETE CASCADE; got: {constraint_def!r}"
    )


# =============================================================================
# Group 7: append_phase_transition() CRUD integration
# =============================================================================


def test_append_phase_transition_inserts_row(db_pool: Any) -> None:
    """Manual append via CRUD: row lands with operator-supplied changed_by + note."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)

    try:
        log_id = append_phase_transition(
            canonical_event_id=seeded_event_id,
            new_phase="live",
            changed_by="human:eric",
            previous_phase="pre_event",
            note=f"Test correction ({suffix})",
        )
        assert isinstance(log_id, int)
        assert log_id > 0

        # Read back via direct SQL to verify shape.
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT canonical_event_id, previous_phase, new_phase,
                       changed_by, note
                FROM canonical_event_phase_log
                WHERE id = %s
                """,
                (log_id,),
            )
            row = cur.fetchone()
        assert row is not None
        assert row["canonical_event_id"] == seeded_event_id
        assert row["previous_phase"] == "pre_event"
        assert row["new_phase"] == "live"
        assert row["changed_by"] == "human:eric"
        assert row["note"] == f"Test correction ({suffix})"
    finally:
        _cleanup_canonical_event(seeded_event_id)


def test_append_phase_transition_invalid_new_phase_raises_value_error(
    db_pool: Any,
) -> None:
    """Manual append with invalid new_phase raises ValueError before SQL.

    Pattern 73 SSOT real-guard discipline: the CRUD validation surfaces
    the error before any DB roundtrip.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)

    try:
        with pytest.raises(ValueError, match="new_phase"):
            append_phase_transition(
                canonical_event_id=seeded_event_id,
                new_phase="not_a_real_phase",
                changed_by="human:eric",
            )
    finally:
        _cleanup_canonical_event(seeded_event_id)


def test_append_phase_transition_invalid_changed_by_raises_value_error(
    db_pool: Any,
) -> None:
    """Manual append with invalid changed_by raises ValueError before SQL."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)

    try:
        with pytest.raises(ValueError, match="changed_by"):
            append_phase_transition(
                canonical_event_id=seeded_event_id,
                new_phase="live",
                changed_by="bad_no_prefix",
            )
    finally:
        _cleanup_canonical_event(seeded_event_id)


def test_append_phase_transition_nonexistent_event_id_raises_fk_violation(
    db_pool: Any,
) -> None:
    """Manual append against a non-existent canonical_event_id raises FK violation."""
    nonexistent_event_id = -999999  # Negative id will not exist
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        append_phase_transition(
            canonical_event_id=nonexistent_event_id,
            new_phase="live",
            changed_by="human:eric",
        )


def test_append_phase_transition_then_read_via_get_phase_history(db_pool: Any) -> None:
    """Append + read: get_phase_history_for_event returns the inserted row."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)

    try:
        # The seed already created 1 row from the trigger; add 1 more manually.
        log_id = append_phase_transition(
            canonical_event_id=seeded_event_id,
            new_phase="resolved",
            changed_by="human:eric",
            previous_phase="live",
            note=f"final ({suffix})",
        )

        history = get_phase_history_for_event(seeded_event_id)
        # 2 rows: 1 from INSERT trigger, 1 from manual append.
        assert len(history) == 2, f"Expected 2 history rows; got {len(history)}"

        # Newest-first ordering: manual append's transition_at >= trigger's.
        # Manual append should be first (or tied; depends on now() resolution).
        ids = [r["id"] for r in history]
        assert log_id in ids, f"Manually-appended row id {log_id} must appear in history"
    finally:
        _cleanup_canonical_event(seeded_event_id)
