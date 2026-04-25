"""Integration tests for migration 0070 -- Cohort 1 carry-forward hardening.

Verifies the POST-MIGRATION state of the two additive integrity fences shipped
by migration 0070 per #1011 council adjudication (ADR-118 V2.40):

    Item 1: Partial UNIQUE index ``uq_canonical_participant_roles_role_when_cross_domain``
            on ``canonical_participant_roles (role) WHERE domain_id IS NULL`` --
            enforces "exactly one cross-domain role per role text" (closes the
            Pattern 81 §"Nullable Parent Scope" gap; PG treats NULL as distinct
            in composite UNIQUE so cross-domain rows could otherwise duplicate).

    Item 3: CHECK constraint ``canonical_events_lifecycle_phase_check``
            restricting ``canonical_events.lifecycle_phase`` to the 8 canonical
            state-machine phases ('proposed', 'listed', 'pre_event', 'live',
            'suspended', 'settling', 'resolved', 'voided').

Test groups:
    - TestPartialUniqueIndex: index exists with correct WHERE clause; behavioral
      exercise of (NULL, 'shared_role') uniqueness vs. domain-scoped duplicate
      tolerance.
    - TestLifecyclePhaseCheck: constraint exists with the 8 expected values;
      behavioral exercise of valid + invalid phase INSERTs.

Issue: #1012 (test coverage) -- migration shipped under #1011 carry-forward bundle.
Epic: #972 (Canonical Layer Foundation -- Phase B.5)
ADR: ADR-118 V2.40 (Cohort 1 Carry-Forward Amendment -- Items 1 + 3)

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


# 8 canonical lifecycle phases per ADR-118 V2.39 line ~17644 inline enumeration.
# This is the SSOT for the test side (Pattern 73 -- the migration owns it in
# code; the test mirrors verbatim).  Drift from the migration => test fails =>
# alignment forced.
_VALID_LIFECYCLE_PHASES: list[str] = [
    "proposed",
    "listed",
    "pre_event",
    "live",
    "suspended",
    "settling",
    "resolved",
    "voided",
]


# =============================================================================
# Group 1: Partial UNIQUE index on canonical_participant_roles
# =============================================================================


def test_partial_unique_index_exists_with_correct_where_clause(db_pool: Any) -> None:
    """``uq_canonical_participant_roles_role_when_cross_domain`` exists with WHERE domain_id IS NULL."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexdef FROM pg_indexes
            WHERE tablename = 'canonical_participant_roles'
              AND indexname = 'uq_canonical_participant_roles_role_when_cross_domain'
            """
        )
        row = cur.fetchone()
    assert row is not None, (
        "uq_canonical_participant_roles_role_when_cross_domain missing post-0070"
    )
    indexdef = row["indexdef"]
    assert "CREATE UNIQUE" in indexdef, f"Index must be UNIQUE; got: {indexdef}"
    assert "(role)" in indexdef, f"Index must be on (role); got: {indexdef}"
    assert "domain_id IS NULL" in indexdef, (
        f"Index must have partial WHERE domain_id IS NULL; got: {indexdef}"
    )


def test_partial_unique_index_blocks_duplicate_cross_domain_role(
    db_pool: Any,
) -> None:
    """Two (NULL, 'shared_role') rows must collide on the partial UNIQUE.

    Behavioral spec: with ``domain_id = NULL``, the partial index enforces
    role-text uniqueness across the cross-domain "shared" rows.  PG would
    otherwise treat NULL as distinct in the composite
    ``uq_canonical_participant_roles_domain_role`` UNIQUE and admit
    duplicates -- this is exactly the gap migration 0070 closes.
    """
    suffix = uuid.uuid4().hex[:8]
    role_text = f"TEST-1012-cross-{suffix}"

    # Cleanup any residue from a prior failed run.
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM canonical_participant_roles WHERE role = %s",
            (role_text,),
        )

    try:
        # First INSERT (NULL, role) succeeds.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_participant_roles (domain_id, role, description)
                VALUES (NULL, %s, %s)
                RETURNING id
                """,
                (role_text, "First cross-domain row"),
            )
            first_id = int(cur.fetchone()["id"])
        assert first_id is not None

        # Second INSERT (NULL, same role) must collide on the partial UNIQUE.
        with pytest.raises(psycopg2.errors.UniqueViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_participant_roles (domain_id, role, description)
                    VALUES (NULL, %s, %s)
                    """,
                    (role_text, "Second cross-domain row -- must collide"),
                )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_participant_roles WHERE role = %s",
                (role_text,),
            )


def test_partial_unique_index_does_not_block_domain_scoped_duplicates(
    db_pool: Any,
) -> None:
    """(domain_id=X, role) and (domain_id=Y, role) both succeed -- partial index does NOT fire.

    The partial WHERE ``domain_id IS NULL`` excludes domain-scoped rows;
    those are governed by the existing composite ``uq_canonical_participant_roles_domain_role``
    UNIQUE, which permits the same role text across different domains.
    """
    suffix = uuid.uuid4().hex[:8]
    role_text = f"TEST-1012-domain-{suffix}"

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM canonical_participant_roles WHERE role = %s",
            (role_text,),
        )

    try:
        # Resolve two distinct seeded domain ids.
        with get_cursor() as cur:
            cur.execute("SELECT id FROM canonical_event_domains WHERE domain = 'sports'")
            sports_id = int(cur.fetchone()["id"])
            cur.execute("SELECT id FROM canonical_event_domains WHERE domain = 'politics'")
            politics_id = int(cur.fetchone()["id"])

        # INSERT (sports, role) and (politics, role) -- both must succeed
        # because the partial index doesn't apply to non-NULL domain_id rows.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_participant_roles (domain_id, role, description)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (sports_id, role_text, "Sports-scoped"),
            )
            id_a = int(cur.fetchone()["id"])

            cur.execute(
                """
                INSERT INTO canonical_participant_roles (domain_id, role, description)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (politics_id, role_text, "Politics-scoped"),
            )
            id_b = int(cur.fetchone()["id"])

        assert id_a != id_b, "Two domain-scoped rows must produce distinct ids"
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_participant_roles WHERE role = %s",
                (role_text,),
            )


# =============================================================================
# Group 2: CHECK constraint on canonical_events.lifecycle_phase
# =============================================================================


def test_lifecycle_phase_check_constraint_exists_with_8_values(db_pool: Any) -> None:
    """``canonical_events_lifecycle_phase_check`` exists with all 8 valid phases."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_events'::regclass
              AND conname = 'canonical_events_lifecycle_phase_check'
            """
        )
        row = cur.fetchone()
    assert row is not None, "canonical_events_lifecycle_phase_check missing post-0070"
    check_def = row["def"]
    for phase in _VALID_LIFECYCLE_PHASES:
        assert phase in check_def, (
            f"CHECK constraint must include phase {phase!r}; got: {check_def}"
        )


@pytest.mark.parametrize("phase", _VALID_LIFECYCLE_PHASES)
def test_lifecycle_phase_check_accepts_each_valid_phase(
    db_pool: Any,
    phase: str,
) -> None:
    """INSERT canonical_events with each of the 8 valid phases must succeed."""
    suffix = uuid.uuid4().hex[:8]
    nk_hash = f"TEST-1012-lp-ok-{phase}-{suffix}".encode()

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM canonical_events WHERE natural_key_hash = %s",
            (nk_hash,),
        )

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_events (
                    domain_id,
                    event_type_id,
                    entities_sorted,
                    resolution_window,
                    natural_key_hash,
                    title,
                    lifecycle_phase
                ) VALUES (
                    (SELECT id FROM canonical_event_domains WHERE domain = 'sports'),
                    (SELECT et.id FROM canonical_event_types et
                     JOIN canonical_event_domains d ON d.id = et.domain_id
                     WHERE d.domain = 'sports' AND et.event_type = 'game'),
                    ARRAY[]::INTEGER[],
                    tstzrange(now(), now() + interval '1 day', '[)'),
                    %s,
                    %s,
                    %s
                )
                RETURNING id
                """,
                (nk_hash, f"Test event ({phase})", phase),
            )
            inserted_id = cur.fetchone()["id"]
        assert inserted_id is not None, (
            f"INSERT with lifecycle_phase={phase!r} must succeed (valid value)"
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_events WHERE natural_key_hash = %s",
                (nk_hash,),
            )


def test_lifecycle_phase_check_blocks_invalid_phase(db_pool: Any) -> None:
    """INSERT canonical_events with an invalid lifecycle_phase must raise CheckViolation."""
    suffix = uuid.uuid4().hex[:8]
    nk_hash = f"TEST-1012-lp-bad-{suffix}".encode()

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM canonical_events WHERE natural_key_hash = %s",
            (nk_hash,),
        )

    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_events (
                        domain_id,
                        event_type_id,
                        entities_sorted,
                        resolution_window,
                        natural_key_hash,
                        title,
                        lifecycle_phase
                    ) VALUES (
                        (SELECT id FROM canonical_event_domains WHERE domain = 'sports'),
                        (SELECT et.id FROM canonical_event_types et
                         JOIN canonical_event_domains d ON d.id = et.domain_id
                         WHERE d.domain = 'sports' AND et.event_type = 'game'),
                        ARRAY[]::INTEGER[],
                        tstzrange(now(), now() + interval '1 day', '[)'),
                        %s,
                        %s,
                        'invalid_phase'
                    )
                    """,
                    (nk_hash, "Test event with invalid phase"),
                )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_events WHERE natural_key_hash = %s",
                (nk_hash,),
            )


def test_lifecycle_phase_check_is_case_sensitive(db_pool: Any) -> None:
    """``'PROPOSED'`` (uppercase) must be rejected -- CHECK is case-sensitive.

    The 8-value vocabulary is all-lowercase per ADR-118 V2.39 line ~17644.
    Uppercase / mixed-case variants must not slip through; if a future
    edit weakens this to a case-insensitive check, this test fails loudly.
    """
    suffix = uuid.uuid4().hex[:8]
    nk_hash = f"TEST-1012-lp-case-{suffix}".encode()

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM canonical_events WHERE natural_key_hash = %s",
            (nk_hash,),
        )

    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_events (
                        domain_id,
                        event_type_id,
                        entities_sorted,
                        resolution_window,
                        natural_key_hash,
                        title,
                        lifecycle_phase
                    ) VALUES (
                        (SELECT id FROM canonical_event_domains WHERE domain = 'sports'),
                        (SELECT et.id FROM canonical_event_types et
                         JOIN canonical_event_domains d ON d.id = et.domain_id
                         WHERE d.domain = 'sports' AND et.event_type = 'game'),
                        ARRAY[]::INTEGER[],
                        tstzrange(now(), now() + interval '1 day', '[)'),
                        %s,
                        %s,
                        'PROPOSED'
                    )
                    """,
                    (nk_hash, "Test event uppercase phase"),
                )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_events WHERE natural_key_hash = %s",
                (nk_hash,),
            )
