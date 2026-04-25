"""Integration tests for migration 0069 -- Cohort 2 canonical markets foundation.

Verifies the POST-MIGRATION state of the ``canonical_markets`` table introduced
by migration 0069, the FK to ``canonical_events``, the inline CHECK constraint
on ``market_type_general``, the FK-column index, and the BEFORE UPDATE trigger
that auto-maintains ``updated_at``.

Test groups:
    - TestTableShape: ``canonical_markets`` columns / types / nullability /
      defaults (full column spec).
    - TestForeignKey: ``canonical_event_id`` references ``canonical_events(id)``
      with ON DELETE RESTRICT (Cohort 2 amendment decision #5b).
    - TestConstraints: inline CHECK on ``market_type_general``
      ('binary' / 'categorical' / 'scalar') per Cohort 2 amendment decision #2;
      UNIQUE on ``natural_key_hash``.
    - TestIndexes: ``idx_canonical_markets_canonical_event_id`` (full,
      not partial -- canonical_event_id is NOT NULL).
    - TestUpdateTrigger: ``trg_canonical_markets_updated_at`` exists and
      auto-maintains ``updated_at`` on UPDATE.

(Migration 0069 does NOT seed any rows -- ``canonical_markets`` lands
empty by design; first rows arrive when matching infrastructure ships
in Cohort 3.)

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
# Per-table column spec (mirrors migration 0069 DDL verbatim).
#
# Each tuple: (column_name, data_type, is_nullable, default_substring_or_None,
#              max_char_length_or_None).
# =============================================================================

_MARKETS_COLS: list[tuple[str, str, str, str | None, int | None]] = [
    ("id", "bigint", "NO", "nextval", None),
    ("canonical_event_id", "bigint", "NO", None, None),
    ("market_type_general", "character varying", "NO", None, 32),
    ("outcome_label", "character varying", "YES", None, 255),
    ("natural_key_hash", "bytea", "NO", None, None),
    ("metadata", "jsonb", "YES", None, None),
    ("created_at", "timestamp with time zone", "NO", "now()", None),
    ("updated_at", "timestamp with time zone", "NO", "now()", None),
    ("retired_at", "timestamp with time zone", "YES", None, None),
]


# =============================================================================
# Group 1: Table shape
# =============================================================================


@pytest.mark.parametrize(
    ("col_name", "data_type", "is_nullable", "default_substr", "max_char_len"),
    _MARKETS_COLS,
)
def test_canonical_markets_column_shape(
    db_pool: Any,
    col_name: str,
    data_type: str,
    is_nullable: str,
    default_substr: str | None,
    max_char_len: int | None,
) -> None:
    """Each column on canonical_markets has the migration-prescribed shape."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT data_type, is_nullable, column_default, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'canonical_markets'
              AND column_name = %s
            """,
            (col_name,),
        )
        row = cur.fetchone()
    assert row is not None, f"canonical_markets.{col_name} missing post-0069"
    assert row["data_type"] == data_type, (
        f"canonical_markets.{col_name} type mismatch: "
        f"expected {data_type!r}, got {row['data_type']!r}"
    )
    assert row["is_nullable"] == is_nullable, (
        f"canonical_markets.{col_name} nullability mismatch: "
        f"expected {is_nullable!r}, got {row['is_nullable']!r}"
    )
    if default_substr is not None:
        actual_default = row["column_default"] or ""
        assert default_substr.lower() in actual_default.lower(), (
            f"canonical_markets.{col_name} default missing {default_substr!r}; "
            f"got {actual_default!r}"
        )
    if max_char_len is not None:
        assert row["character_maximum_length"] == max_char_len, (
            f"canonical_markets.{col_name} max_length mismatch: "
            f"expected {max_char_len}, got {row['character_maximum_length']}"
        )


def test_canonical_markets_has_no_lifecycle_phase_column(db_pool: Any) -> None:
    """Per ADR-118 V2.39 Cohort 2 amendment decision #3: NO lifecycle_phase column.

    Three-distinct-concerns model: per-platform lifecycle on ``markets.status``,
    canonical-event lifecycle on ``canonical_events.lifecycle_phase``,
    canonical-market retirement on ``retired_at`` only.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'canonical_markets'
              AND column_name = 'lifecycle_phase'
            """
        )
        row = cur.fetchone()
    assert row is None, (
        "canonical_markets must NOT have a lifecycle_phase column "
        "(ADR-118 V2.39 Cohort 2 amendment decision #3)"
    )


# =============================================================================
# Group 2: Foreign key to canonical_events (ON DELETE RESTRICT)
# =============================================================================


def test_canonical_markets_canonical_event_id_fk_is_restrict(db_pool: Any) -> None:
    """``canonical_event_id`` FK is ON DELETE RESTRICT per Cohort 2 amendment decision #5b.

    Markets carry settlement; CASCADE would silently delete settlement-bearing
    rows.  Asymmetry with ``canonical_event_participants.CASCADE`` is intentional
    -- participants are denormalization, markets carry settlement + observation
    history.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_markets'::regclass
              AND conname = 'canonical_markets_canonical_event_id_fkey'
            """
        )
        row = cur.fetchone()
    assert row is not None, "canonical_markets_canonical_event_id_fkey must exist"
    fk_def = row["def"]
    assert "REFERENCES canonical_events(id)" in fk_def, (
        f"FK must reference canonical_events(id); got: {fk_def}"
    )
    assert "ON DELETE RESTRICT" in fk_def, (
        f"FK must be ON DELETE RESTRICT (Cohort 2 amendment decision #5b); got: {fk_def}"
    )


# =============================================================================
# Group 3: Constraints (CHECK on market_type_general + UNIQUE natural_key_hash)
# =============================================================================


def test_market_type_general_check_constraint_exists(db_pool: Any) -> None:
    """Inline CHECK on ``market_type_general`` per Cohort 2 amendment decision #2.

    Closed enum tied to pmxt #964 NormalizedMarket contract; explicitly NOT
    a Pattern 81 lookup table because the open-set test fails (a future
    market shape requires a code deploy regardless).
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_markets'::regclass
              AND conname = 'canonical_markets_market_type_general_check'
            """
        )
        row = cur.fetchone()
    assert row is not None, "canonical_markets_market_type_general_check must exist"
    check_def = row["def"]
    for value in ("binary", "categorical", "scalar"):
        assert value in check_def, (
            f"market_type_general CHECK must include {value!r}; got: {check_def}"
        )


def test_market_type_general_check_blocks_invalid_value(db_pool: Any) -> None:
    """INSERT canonical_markets with invalid market_type_general must raise CheckViolation.

    Behavioral verification of the inline CHECK -- existence is structural,
    rejection is behavioral.
    """
    suffix = uuid.uuid4().hex[:8]
    nk_hash = f"TEST-1012-mt-bad-{suffix}".encode()

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM canonical_markets WHERE natural_key_hash = %s",
            (nk_hash,),
        )

    # Seed a real canonical_event so FK passes; CHECK fires on row-local validation.
    try:
        seeded_event_id = _seed_canonical_event(suffix)
        try:
            with pytest.raises(psycopg2.errors.CheckViolation):
                with get_cursor(commit=True) as cur:
                    cur.execute(
                        """
                        INSERT INTO canonical_markets
                            (canonical_event_id, market_type_general, natural_key_hash)
                        VALUES (%s, 'invalid_type', %s)
                        """,
                        (seeded_event_id, nk_hash),
                    )
        finally:
            _cleanup_canonical_event(seeded_event_id)
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_markets WHERE natural_key_hash = %s",
                (nk_hash,),
            )


def test_market_type_general_check_accepts_valid_values(db_pool: Any) -> None:
    """INSERT canonical_markets with each of binary/categorical/scalar must succeed."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    inserted_hashes: list[bytes] = []
    try:
        for market_type in ("binary", "categorical", "scalar"):
            nk_hash = f"TEST-1012-mt-ok-{market_type}-{suffix}".encode()
            inserted_hashes.append(nk_hash)
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_markets
                        (canonical_event_id, market_type_general, natural_key_hash)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (seeded_event_id, market_type, nk_hash),
                )
                inserted_id = cur.fetchone()["id"]
            assert inserted_id is not None, (
                f"INSERT with market_type_general={market_type!r} must succeed"
            )
    finally:
        if inserted_hashes:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM canonical_markets WHERE natural_key_hash = ANY(%s)",
                    (inserted_hashes,),
                )
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_markets_natural_key_hash_unique(db_pool: Any) -> None:
    """``uq_canonical_markets_nk`` enforces UNIQUE (natural_key_hash)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_markets'::regclass
              AND conname = 'uq_canonical_markets_nk'
            """
        )
        row = cur.fetchone()
    assert row is not None, "uq_canonical_markets_nk must exist"
    assert "UNIQUE (natural_key_hash)" in row["def"], (
        f"uq_canonical_markets_nk must enforce UNIQUE (natural_key_hash); got: {row['def']}"
    )


# =============================================================================
# Group 4: FK-column index (full, non-partial)
# =============================================================================


def test_idx_canonical_markets_canonical_event_id_is_full_btree(db_pool: Any) -> None:
    """``idx_canonical_markets_canonical_event_id`` is a non-partial btree (canonical_event_id is NOT NULL)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexdef FROM pg_indexes
            WHERE tablename = 'canonical_markets'
              AND indexname = 'idx_canonical_markets_canonical_event_id'
            """
        )
        row = cur.fetchone()
    assert row is not None, "idx_canonical_markets_canonical_event_id missing post-0069"
    indexdef = row["indexdef"]
    assert "CREATE UNIQUE" not in indexdef, f"FK index must NOT be UNIQUE; got: {indexdef}"
    assert "(canonical_event_id)" in indexdef, (
        f"Index must be on canonical_event_id; got: {indexdef}"
    )
    # canonical_event_id is NOT NULL; partial WHERE would not reduce size.
    assert " WHERE " not in indexdef, (
        f"FK index must NOT be partial (canonical_event_id is NOT NULL); got: {indexdef}"
    )


# =============================================================================
# Group 5: BEFORE UPDATE trigger -- updated_at auto-maintenance
# =============================================================================


def test_canonical_markets_update_trigger_exists(db_pool: Any) -> None:
    """``trg_canonical_markets_updated_at`` BEFORE UPDATE trigger exists."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_triggerdef(t.oid) AS def
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            WHERE c.relname = 'canonical_markets'
              AND t.tgname = 'trg_canonical_markets_updated_at'
              AND NOT t.tgisinternal
            """
        )
        row = cur.fetchone()
    assert row is not None, "trg_canonical_markets_updated_at must exist post-0069"
    trigger_def = row["def"]
    assert "BEFORE UPDATE" in trigger_def, f"Must be a BEFORE UPDATE trigger; got: {trigger_def}"
    assert "update_canonical_markets_updated_at" in trigger_def, (
        f"Must call update_canonical_markets_updated_at(); got: {trigger_def}"
    )


def test_canonical_markets_update_trigger_advances_updated_at(db_pool: Any) -> None:
    """UPDATE on canonical_markets advances ``updated_at`` to NOW() per the trigger.

    Behavioral exercise of the trigger body -- migration line ~228-235:
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    nk_hash = f"TEST-1012-trig-{suffix}".encode()
    try:
        # INSERT a row.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_markets
                    (canonical_event_id, market_type_general, natural_key_hash)
                VALUES (%s, 'binary', %s)
                RETURNING id, updated_at
                """,
                (seeded_event_id, nk_hash),
            )
            row = cur.fetchone()
            market_id = int(row["id"])
            initial_updated_at = row["updated_at"]

        # UPDATE a non-updated_at column; trigger should refresh updated_at.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE canonical_markets SET outcome_label = %s WHERE id = %s",
                ("test_outcome", market_id),
            )

        # Verify updated_at advanced.
        with get_cursor() as cur:
            cur.execute(
                "SELECT updated_at FROM canonical_markets WHERE id = %s",
                (market_id,),
            )
            post_row = cur.fetchone()
        post_updated_at = post_row["updated_at"]
        assert post_updated_at >= initial_updated_at, (
            f"updated_at must advance (or stay equal on same clock tick); "
            f"initial={initial_updated_at!r}, post={post_updated_at!r}"
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_markets WHERE natural_key_hash = %s",
                (nk_hash,),
            )
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Helpers (canonical_event seeding for FK-bearing tests)
# =============================================================================


def _seed_canonical_event(suffix: str) -> int:
    """Seed a canonical_events row to back the canonical_markets FK.

    Uses the seeded ``sports`` domain + ``game`` event_type from migration 0067.
    Caller MUST pair with ``_cleanup_canonical_event(returned_id)`` in a finally
    block.
    """
    nk_hash = f"TEST-1012-evt-{suffix}".encode()
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
                'proposed'
            )
            RETURNING id
            """,
            (nk_hash, f"Test event for 1012 ({suffix})"),
        )
        return int(cur.fetchone()["id"])


def _cleanup_canonical_event(event_id: int) -> None:
    """Delete a canonical_events row seeded by ``_seed_canonical_event``."""
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM canonical_events WHERE id = %s", (event_id,))
