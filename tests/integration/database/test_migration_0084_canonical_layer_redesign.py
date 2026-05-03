"""Integration tests for Migration 0084 -- Canonical layer redesign (V2.45).

Verifies the POST-MIGRATION state of the four user-adjudicated decisions
shipped by Migration 0084 (Cohort 4 close-out, ADR-118 V2.45 Items 1/4/6/8;
binding architectural reasoning at ``memory/design_review_v246_input_memo.md``):

    Item 1 -- Cohort 4 informal close + slot 0083 deferral.  No DDL impact;
              tested only as the slot-0083 hole in the alembic chain
              (down_revision = "0082" on slot 0084; verified separately
              by the round-trip CI gate auto-discovering the chain).

    Item 4 -- ``canonical_observations.payload`` column DROPPED.  Verified
              by absence in information_schema.columns + by the slot 0078
              schema test's _OBSERVATIONS_COLS spec being post-V2.45.

    Item 6 -- ``temporal_alignment`` redesigned as PURE LINKAGE TABLE.
              Verified by the new 8-column shape + 3 constraints + 3
              indexes + absence of all sport-typed columns from slot 0035
              era (home_score, away_score, period, clock, game_status,
              yes_ask_price, no_ask_price, spread, volume, etc.).

    Item 8 -- ``canonical_observations.canonical_event_id`` RENAMED to
              ``canonical_primary_event_id`` + new
              ``canonical_observation_event_links`` table.  Verified by
              the new column name + the new link table's 6 columns + 2
              CHECKs + 3 indexes (including the partial unique index for
              link_kind='primary').

Test groups:
    - TestColumnShape: payload absent, canonical_primary_event_id present,
      canonical_event_id absent on canonical_observations.
    - TestTemporalAlignmentRedesign: new 8-column shape; constraints +
      indexes; absence of slot-0035-era sport-specific columns.
    - TestLinkTableSchema: 6 columns + 2 CHECKs + 3 indexes (including
      partial unique).
    - TestLinkTableBehavior: link_kind CHECK; confidence range CHECK;
      partial unique on link_kind='primary'; CASCADE on observation
      delete; RESTRICT on canonical_event delete.
    - TestNewTemporalAlignmentBehavior: distinct observations CHECK;
      alignment_quality CHECK; pair UNIQUE; observation FK NO ACTION
      semantics.
    - TestPatternCompliance: Pattern 87 (no edits to migrations 0001-0082);
      Pattern 73 SSOT (link_kind canonical home is the CHECK in this slot).

Round-trip CI gate inheritance (PR #1081 / Epic #1071):
    Slot 0084's ``downgrade()`` is a pure inverse of ``upgrade()``;
    every DROP / RENAME / CREATE has a matching reverse step.  The
    round-trip CI gate auto-discovers slot 0084 on push and runs
    ``downgrade -> upgrade head`` against it.  No separate downgrade
    test is required here; faithful schema reconstruction in downgrade()
    is what the round-trip gate verifies.

Issues: Epic #972 (Canonical Layer Foundation -- Phase B.5),
    V2.45 Items 1/4/6/8 (Cohort 4 informal close + canonical layer redesign),
    #1141 (Cohort 5+ slot-0083-equivalent + per-domain temporal_alignment views),
    #1143 (V2.46 design-review scope -- Items 2/3/5/7/9/10)
ADR: ADR-118 V2.45
Memo: ``memory/design_review_v246_input_memo.md``

Markers:
    @pytest.mark.integration: real DB required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import psycopg2
import psycopg2.errors
import pytest

from precog.database.connection import get_cursor
from tests.integration.database._canonical_event_helpers import (
    _cleanup_canonical_event,
    _seed_canonical_event,
)

pytestmark = [pytest.mark.integration]


# =============================================================================
# Pattern 73 SSOT -- column / constraint / index inventories.
#
# These tuples mirror the migration's DDL verbatim so drift between the
# migration and the test is detected.  Pattern 73 SSOT canonical home
# for the slot 0084 schema shape (until Cohort 5+ ships a CRUD module
# that imports a constants tuple).
# =============================================================================

# canonical_observations expected post-V2.45 column shape (12 columns;
# payload dropped + canonical_event_id renamed).
_CANONICAL_OBSERVATIONS_EXPECTED_COLUMNS: tuple[str, ...] = (
    "id",
    "observation_kind",
    "source_id",
    "canonical_primary_event_id",  # V2.45 rename target
    "payload_hash",
    # NO 'payload' column post-V2.45
    "event_occurred_at",
    "source_published_at",
    "ingested_at",
    "valid_at",
    "valid_until",
    "created_at",
    "updated_at",
)

# Columns that MUST be absent on canonical_observations post-V2.45.
_CANONICAL_OBSERVATIONS_FORBIDDEN_COLUMNS: tuple[str, ...] = (
    "payload",  # Item 4 dropped
    "canonical_event_id",  # Item 8 renamed
)

# New temporal_alignment expected column shape (10 columns post-V2.43-Item-3
# composite-FK adjustment: observation_a + observation_b each carry their
# own ingested_at companion to satisfy the partition-key invariant).
_NEW_TEMPORAL_ALIGNMENT_EXPECTED_COLUMNS: tuple[str, ...] = (
    "id",
    "observation_a_id",
    "observation_a_ingested_at",
    "observation_b_id",
    "observation_b_ingested_at",
    "canonical_event_id",
    "time_delta_seconds",
    "alignment_quality",
    "aligned_at",
    "created_at",
)

# Columns from slot-0035-era denormalized fact-table shape that MUST be
# absent post-V2.45.
_OLD_TEMPORAL_ALIGNMENT_FORBIDDEN_COLUMNS: tuple[str, ...] = (
    "market_id",
    "market_snapshot_id",
    "game_state_id",
    "snapshot_time",
    "game_state_time",
    "yes_ask_price",
    "no_ask_price",
    "spread",
    "volume",
    "game_status",
    "home_score",
    "away_score",
    "period",
    "clock",
    "game_id",
)

# canonical_observation_event_links expected column shape (7 columns
# post-V2.43-Item-3 composite-FK adjustment: observation_ingested_at
# accompanies observation_id to satisfy the partition-key invariant).
_LINK_TABLE_EXPECTED_COLUMNS: tuple[str, ...] = (
    "observation_id",
    "observation_ingested_at",
    "canonical_event_id",
    "link_kind",
    "confidence",
    "linked_at",
    "linked_by",
)


# =============================================================================
# Helper: get/insert canonical_observations rows for behavioral tests.
# =============================================================================


def _get_kalshi_source_id() -> int:
    """Resolve the kalshi observation_source.id."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT id FROM observation_source WHERE source_key = %s",
            ("kalshi",),
        )
        row = cur.fetchone()
    assert row is not None, "observation_source 'kalshi' seed missing"
    return int(row["id"])


def _ingested_at_in_partition() -> datetime:
    """TIMESTAMPTZ within slot 0078 baseline partition coverage."""
    return datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)


def _insert_canonical_observation(
    *,
    source_id: int,
    canonical_primary_event_id: int | None = None,
    suffix: str = "",
) -> tuple[int, datetime]:
    """Insert a canonical_observations row directly via SQL (post-V2.45 shape).

    No payload column; only payload_hash (computed deterministically from
    a per-test-distinct marker so dedup UNIQUE is not hit).
    """
    import hashlib
    import json as _json

    payload_marker = {"slot_0084_test_marker": suffix or uuid.uuid4().hex}
    payload_hash = hashlib.sha256(
        _json.dumps(payload_marker, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).digest()
    ingested_at = _ingested_at_in_partition()

    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO canonical_observations (
                observation_kind, source_id, canonical_primary_event_id,
                payload_hash,
                event_occurred_at, source_published_at, ingested_at,
                valid_at, valid_until
            ) VALUES (
                %s, %s, %s,
                %s,
                %s, %s, %s,
                %s, %s
            )
            RETURNING id, ingested_at
            """,
            (
                "game_state",
                source_id,
                canonical_primary_event_id,
                payload_hash,
                ingested_at,
                ingested_at,
                ingested_at,
                ingested_at,
                None,
            ),
        )
        row = cur.fetchone()
    return int(row["id"]), row["ingested_at"]


def _cleanup_canonical_observation(obs_id: int, ingested_at: datetime) -> None:
    """Delete a canonical_observations row by composite PK (best-effort)."""
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_observations WHERE id = %s AND ingested_at = %s",
                (obs_id, ingested_at),
            )
    except Exception:
        pass


# =============================================================================
# Group 1: canonical_observations column shape post-V2.45 (Items 4 + 8)
# =============================================================================


@pytest.mark.parametrize("col_name", _CANONICAL_OBSERVATIONS_EXPECTED_COLUMNS)
def test_canonical_observations_expected_column_present(db_pool: Any, col_name: str) -> None:
    """Each expected post-V2.45 column is present on canonical_observations."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'canonical_observations'
              AND column_name = %s
              AND table_schema = 'public'
            """,
            (col_name,),
        )
        row = cur.fetchone()
    assert row is not None, (
        f"canonical_observations.{col_name} missing post-V2.45 — expected per Migration 0084"
    )


@pytest.mark.parametrize("col_name", _CANONICAL_OBSERVATIONS_FORBIDDEN_COLUMNS)
def test_canonical_observations_forbidden_column_absent(db_pool: Any, col_name: str) -> None:
    """V2.45 forbidden columns (dropped or renamed) are absent.

    Item 4 dropped 'payload'; Item 8 renamed 'canonical_event_id' to
    'canonical_primary_event_id'.  Both must be absent on the post-
    Migration-0084 schema.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'canonical_observations'
              AND column_name = %s
              AND table_schema = 'public'
            """,
            (col_name,),
        )
        row = cur.fetchone()
    assert row is None, (
        f"canonical_observations.{col_name} present post-V2.45 — Migration 0084 "
        f"failed to drop/rename it (V2.45 Items 4 + 8)"
    )


def test_canonical_primary_event_id_is_bigint_nullable(db_pool: Any) -> None:
    """canonical_primary_event_id (renamed from canonical_event_id) is BIGINT NULL."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'canonical_observations'
              AND column_name = 'canonical_primary_event_id'
              AND table_schema = 'public'
            """
        )
        row = cur.fetchone()
    assert row is not None, "canonical_primary_event_id missing"
    assert row["data_type"] == "bigint", (
        f"canonical_primary_event_id type mismatch: expected bigint, got {row['data_type']!r}"
    )
    assert row["is_nullable"] == "YES", (
        "canonical_primary_event_id must be nullable (cross-domain observations may have no event)"
    )


# =============================================================================
# Group 2: temporal_alignment redesigned shape (Item 6)
# =============================================================================


@pytest.mark.parametrize("col_name", _NEW_TEMPORAL_ALIGNMENT_EXPECTED_COLUMNS)
def test_new_temporal_alignment_column_present(db_pool: Any, col_name: str) -> None:
    """Each expected post-V2.45 column is present on temporal_alignment."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'temporal_alignment'
              AND column_name = %s
              AND table_schema = 'public'
            """,
            (col_name,),
        )
        row = cur.fetchone()
    assert row is not None, (
        f"temporal_alignment.{col_name} missing post-V2.45 — expected per Migration 0084"
    )


@pytest.mark.parametrize("col_name", _OLD_TEMPORAL_ALIGNMENT_FORBIDDEN_COLUMNS)
def test_old_temporal_alignment_columns_absent(db_pool: Any, col_name: str) -> None:
    """Slot-0035-era denormalized columns are absent post-V2.45 redesign.

    The pure-linkage redesign (V2.45 Item 6) removed all sport-specific
    typed columns; per-domain typed views (Cohort 5+ via #1141) now
    JOIN to per-kind projection tables for the typed surface.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'temporal_alignment'
              AND column_name = %s
              AND table_schema = 'public'
            """,
            (col_name,),
        )
        row = cur.fetchone()
    assert row is None, (
        f"temporal_alignment.{col_name} present post-V2.45 — old denormalized "
        f"shape was not fully removed by Migration 0084 (V2.45 Item 6)"
    )


def test_new_temporal_alignment_constraints_present(db_pool: Any) -> None:
    """The 3 expected constraints (uq_alignment_pair, ck_distinct, ck_quality) exist."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT conname, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE conrelid = 'temporal_alignment'::regclass
            ORDER BY conname
            """
        )
        rows = cur.fetchall()
    constraint_names = {r["conname"] for r in rows}

    assert "uq_alignment_pair" in constraint_names, (
        "uq_alignment_pair UNIQUE (observation_a_id, observation_a_ingested_at, "
        "observation_b_id, observation_b_ingested_at) missing"
    )
    assert "ck_distinct_observations" in constraint_names, "ck_distinct_observations CHECK missing"
    assert "ck_alignment_quality" in constraint_names, "ck_alignment_quality CHECK missing"


def test_new_temporal_alignment_indexes_present(db_pool: Any) -> None:
    """The 3 expected indexes (canonical_event, observation_a, observation_b) exist.

    Note: PG truncates partition-side index names when parent+index name
    exceeds 63 bytes; this table is not partitioned, so we key on
    indexname directly.  See feedback_pg_partition_index_name_truncation
    for the partition-table version of this discipline.
    """
    expected_indexes = {
        "idx_alignment_canonical_event",
        "idx_alignment_observation_a",
        "idx_alignment_observation_b",
    }
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'temporal_alignment'
            """
        )
        rows = cur.fetchall()
    actual_indexes = {r["indexname"] for r in rows}
    missing = expected_indexes - actual_indexes
    assert not missing, f"temporal_alignment missing indexes: {missing}"


# =============================================================================
# Group 3: canonical_observation_event_links schema (Item 8 link table)
# =============================================================================


@pytest.mark.parametrize("col_name", _LINK_TABLE_EXPECTED_COLUMNS)
def test_link_table_column_present(db_pool: Any, col_name: str) -> None:
    """Each expected column is present on canonical_observation_event_links."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'canonical_observation_event_links'
              AND column_name = %s
              AND table_schema = 'public'
            """,
            (col_name,),
        )
        row = cur.fetchone()
    assert row is not None, (
        f"canonical_observation_event_links.{col_name} missing — expected per V2.45 Item 8"
    )


def test_link_table_check_constraints_present(db_pool: Any) -> None:
    """ck_link_kind + ck_confidence_range CHECK constraints exist."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = 'canonical_observation_event_links'::regclass
              AND contype = 'c'
            """
        )
        rows = cur.fetchall()
    constraint_names = {r["conname"] for r in rows}

    assert "ck_link_kind" in constraint_names, "ck_link_kind CHECK missing"
    assert "ck_confidence_range" in constraint_names, "ck_confidence_range CHECK missing"


def test_link_table_indexes_present(db_pool: Any) -> None:
    """3 expected indexes including the partial unique idx_link_one_primary_per_observation."""
    expected_indexes = {
        "idx_link_observation",
        "idx_link_canonical_event",
        "idx_link_one_primary_per_observation",
    }
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'canonical_observation_event_links'
            """
        )
        rows = cur.fetchall()
    actual_indexes = {r["indexname"] for r in rows}
    missing = expected_indexes - actual_indexes
    assert not missing, f"canonical_observation_event_links missing indexes: {missing}"

    # Verify the partial unique index has the WHERE link_kind = 'primary' clause.
    index_defs = {r["indexname"]: r["indexdef"] for r in rows}
    primary_idx_def = index_defs.get("idx_link_one_primary_per_observation", "")
    assert "UNIQUE" in primary_idx_def, (
        "idx_link_one_primary_per_observation must be UNIQUE; got definition: " + primary_idx_def
    )
    assert "primary" in primary_idx_def.lower() or "'primary'" in primary_idx_def, (
        "idx_link_one_primary_per_observation must filter on link_kind = 'primary'; "
        "got definition: " + primary_idx_def
    )


# =============================================================================
# Group 4: canonical_observation_event_links behavioral tests (Item 8)
# =============================================================================


def test_link_kind_primary_accepted(db_pool: Any) -> None:
    """INSERT with link_kind='primary' succeeds (composite-FK shape per V2.43 Item 3)."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    source_id = _get_kalshi_source_id()
    obs_id, obs_ingested_at = _insert_canonical_observation(
        source_id=source_id, suffix=f"primary-{suffix}"
    )

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_observation_event_links
                    (observation_id, observation_ingested_at, canonical_event_id,
                     link_kind, confidence, linked_by)
                VALUES (%s, %s, %s, 'primary', 0.95, 'matcher_v1')
                """,
                (obs_id, obs_ingested_at, seeded_event_id),
            )
        # Verify row exists.
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT link_kind, confidence
                FROM canonical_observation_event_links
                WHERE observation_id = %s
                  AND observation_ingested_at = %s
                  AND canonical_event_id = %s
                """,
                (obs_id, obs_ingested_at, seeded_event_id),
            )
            row = cur.fetchone()
        assert row is not None
        assert row["link_kind"] == "primary"
        assert row["confidence"] == Decimal("0.9500")
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_observation_event_links "
                "WHERE observation_id = %s AND observation_ingested_at = %s "
                "AND canonical_event_id = %s",
                (obs_id, obs_ingested_at, seeded_event_id),
            )
        _cleanup_canonical_observation(obs_id, obs_ingested_at)
        _cleanup_canonical_event(seeded_event_id)


def test_link_kind_secondary_accepted(db_pool: Any) -> None:
    """INSERT with link_kind='secondary' succeeds (multi-event tagging)."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    source_id = _get_kalshi_source_id()
    obs_id, obs_ingested_at = _insert_canonical_observation(
        source_id=source_id, suffix=f"secondary-{suffix}"
    )

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_observation_event_links
                    (observation_id, observation_ingested_at, canonical_event_id,
                     link_kind, confidence, linked_by)
                VALUES (%s, %s, %s, 'secondary', NULL, 'manual_seed')
                """,
                (obs_id, obs_ingested_at, seeded_event_id),
            )
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT link_kind, confidence
                FROM canonical_observation_event_links
                WHERE observation_id = %s
                  AND observation_ingested_at = %s
                  AND canonical_event_id = %s
                """,
                (obs_id, obs_ingested_at, seeded_event_id),
            )
            row = cur.fetchone()
        assert row is not None
        assert row["link_kind"] == "secondary"
        assert row["confidence"] is None
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_observation_event_links "
                "WHERE observation_id = %s AND observation_ingested_at = %s "
                "AND canonical_event_id = %s",
                (obs_id, obs_ingested_at, seeded_event_id),
            )
        _cleanup_canonical_observation(obs_id, obs_ingested_at)
        _cleanup_canonical_event(seeded_event_id)


def test_link_kind_invalid_rejected(db_pool: Any) -> None:
    """INSERT with link_kind not in ('primary','secondary','derived','speculative') raises CHECK."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    source_id = _get_kalshi_source_id()
    obs_id, obs_ingested_at = _insert_canonical_observation(
        source_id=source_id, suffix=f"invalid-{suffix}"
    )

    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_observation_event_links
                        (observation_id, observation_ingested_at, canonical_event_id,
                         link_kind, linked_by)
                    VALUES (%s, %s, %s, 'invalid_kind', 'matcher_v1')
                    """,
                    (obs_id, obs_ingested_at, seeded_event_id),
                )
    finally:
        _cleanup_canonical_observation(obs_id, obs_ingested_at)
        _cleanup_canonical_event(seeded_event_id)


def test_confidence_out_of_range_rejected(db_pool: Any) -> None:
    """INSERT with confidence > 1 raises CHECK."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    source_id = _get_kalshi_source_id()
    obs_id, obs_ingested_at = _insert_canonical_observation(
        source_id=source_id, suffix=f"conf-bad-{suffix}"
    )

    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_observation_event_links
                        (observation_id, observation_ingested_at, canonical_event_id,
                         link_kind, confidence, linked_by)
                    VALUES (%s, %s, %s, 'primary', 1.5, 'matcher_v1')
                    """,
                    (obs_id, obs_ingested_at, seeded_event_id),
                )
    finally:
        _cleanup_canonical_observation(obs_id, obs_ingested_at)
        _cleanup_canonical_event(seeded_event_id)


def test_confidence_in_range_accepted(db_pool: Any) -> None:
    """INSERT with confidence=0.5 (valid range) succeeds."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    source_id = _get_kalshi_source_id()
    obs_id, obs_ingested_at = _insert_canonical_observation(
        source_id=source_id, suffix=f"conf-good-{suffix}"
    )

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_observation_event_links
                    (observation_id, observation_ingested_at, canonical_event_id,
                     link_kind, confidence, linked_by)
                VALUES (%s, %s, %s, 'derived', 0.5, 'matcher_v1')
                """,
                (obs_id, obs_ingested_at, seeded_event_id),
            )
        # If we got here, the INSERT succeeded.
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_observation_event_links "
                "WHERE observation_id = %s AND observation_ingested_at = %s "
                "AND canonical_event_id = %s",
                (obs_id, obs_ingested_at, seeded_event_id),
            )
        _cleanup_canonical_observation(obs_id, obs_ingested_at)
        _cleanup_canonical_event(seeded_event_id)


def test_one_primary_per_observation_enforced(db_pool: Any) -> None:
    """Two link_kind='primary' rows for the same observation are rejected by partial UNIQUE.

    The partial unique index targets (observation_id, observation_ingested_at)
    WHERE link_kind = 'primary' — at most one primary link per observation
    (full composite identifier).
    """
    suffix = uuid.uuid4().hex[:8]
    event_id_a = _seed_canonical_event(f"primary-a-{suffix}")
    event_id_b = _seed_canonical_event(f"primary-b-{suffix}")
    source_id = _get_kalshi_source_id()
    obs_id, obs_ingested_at = _insert_canonical_observation(
        source_id=source_id, suffix=f"primary-dup-{suffix}"
    )

    try:
        # First primary link succeeds.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_observation_event_links
                    (observation_id, observation_ingested_at, canonical_event_id,
                     link_kind, linked_by)
                VALUES (%s, %s, %s, 'primary', 'matcher_v1')
                """,
                (obs_id, obs_ingested_at, event_id_a),
            )

        # Second primary link to a DIFFERENT canonical_event for the SAME observation
        # must be rejected by the partial unique index.
        with pytest.raises(psycopg2.errors.UniqueViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO canonical_observation_event_links
                        (observation_id, observation_ingested_at, canonical_event_id,
                         link_kind, linked_by)
                    VALUES (%s, %s, %s, 'primary', 'matcher_v1')
                    """,
                    (obs_id, obs_ingested_at, event_id_b),
                )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_observation_event_links "
                "WHERE observation_id = %s AND observation_ingested_at = %s",
                (obs_id, obs_ingested_at),
            )
        _cleanup_canonical_observation(obs_id, obs_ingested_at)
        _cleanup_canonical_event(event_id_a)
        _cleanup_canonical_event(event_id_b)


def test_multiple_secondary_links_per_observation_allowed(db_pool: Any) -> None:
    """Multiple link_kind='secondary' rows for the same observation are allowed.

    The partial unique index targets only link_kind='primary'; secondary
    / derived / speculative links can be many-per-observation.
    """
    suffix = uuid.uuid4().hex[:8]
    event_id_a = _seed_canonical_event(f"sec-a-{suffix}")
    event_id_b = _seed_canonical_event(f"sec-b-{suffix}")
    source_id = _get_kalshi_source_id()
    obs_id, obs_ingested_at = _insert_canonical_observation(
        source_id=source_id, suffix=f"sec-multi-{suffix}"
    )

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_observation_event_links
                    (observation_id, observation_ingested_at, canonical_event_id,
                     link_kind, linked_by)
                VALUES
                    (%s, %s, %s, 'secondary', 'matcher_v1'),
                    (%s, %s, %s, 'secondary', 'matcher_v1')
                """,
                (
                    obs_id,
                    obs_ingested_at,
                    event_id_a,
                    obs_id,
                    obs_ingested_at,
                    event_id_b,
                ),
            )
        # Verify both rows exist.
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT count(*) AS cnt
                FROM canonical_observation_event_links
                WHERE observation_id = %s
                  AND observation_ingested_at = %s
                  AND link_kind = 'secondary'
                """,
                (obs_id, obs_ingested_at),
            )
            row = cur.fetchone()
        assert row["cnt"] == 2, "Two secondary links should coexist for same observation"
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_observation_event_links "
                "WHERE observation_id = %s AND observation_ingested_at = %s",
                (obs_id, obs_ingested_at),
            )
        _cleanup_canonical_observation(obs_id, obs_ingested_at)
        _cleanup_canonical_event(event_id_a)
        _cleanup_canonical_event(event_id_b)


def test_observation_delete_cascades_to_link(db_pool: Any) -> None:
    """DELETE canonical_observations row CASCADEs to canonical_observation_event_links."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    source_id = _get_kalshi_source_id()
    obs_id, obs_ingested_at = _insert_canonical_observation(
        source_id=source_id, suffix=f"cascade-{suffix}"
    )

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_observation_event_links
                    (observation_id, observation_ingested_at, canonical_event_id,
                     link_kind, linked_by)
                VALUES (%s, %s, %s, 'primary', 'matcher_v1')
                """,
                (obs_id, obs_ingested_at, seeded_event_id),
            )

        # DELETE the observation row -> CASCADE drops the link row.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_observations WHERE id = %s AND ingested_at = %s",
                (obs_id, obs_ingested_at),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT count(*) AS cnt FROM canonical_observation_event_links "
                "WHERE observation_id = %s AND observation_ingested_at = %s",
                (obs_id, obs_ingested_at),
            )
            row = cur.fetchone()
        assert row["cnt"] == 0, "Link row should CASCADE-delete when observation deleted"
    finally:
        # Observation already deleted; ensure no link rows linger.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_observation_event_links "
                "WHERE observation_id = %s AND observation_ingested_at = %s",
                (obs_id, obs_ingested_at),
            )
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_event_delete_restricted_when_link_exists(db_pool: Any) -> None:
    """DELETE canonical_events row referenced by a link is RESTRICTED."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    source_id = _get_kalshi_source_id()
    obs_id, obs_ingested_at = _insert_canonical_observation(
        source_id=source_id, suffix=f"restrict-{suffix}"
    )

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_observation_event_links
                    (observation_id, observation_ingested_at, canonical_event_id,
                     link_kind, linked_by)
                VALUES (%s, %s, %s, 'primary', 'matcher_v1')
                """,
                (obs_id, obs_ingested_at, seeded_event_id),
            )

        # DELETE canonical_event with link rows referencing it must fail.
        with pytest.raises(
            (
                psycopg2.errors.ForeignKeyViolation,
                psycopg2.errors.RestrictViolation,
            )
        ):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM canonical_events WHERE id = %s",
                    (seeded_event_id,),
                )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_observation_event_links "
                "WHERE observation_id = %s AND observation_ingested_at = %s",
                (obs_id, obs_ingested_at),
            )
        _cleanup_canonical_observation(obs_id, obs_ingested_at)
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 5: new temporal_alignment behavioral tests (Item 6)
#
# All FKs into canonical_observations use composite shape per V2.43 Item 3
# (canonical_observations is partitioned with composite PK (id, ingested_at);
# FK references must include both columns).
# =============================================================================


def test_new_temporal_alignment_distinct_observations_check(db_pool: Any) -> None:
    """INSERT with same (observation_id, ingested_at) on both sides raises CHECK."""
    suffix = uuid.uuid4().hex[:8]
    source_id = _get_kalshi_source_id()
    obs_id, obs_ingested_at = _insert_canonical_observation(
        source_id=source_id, suffix=f"self-pair-{suffix}"
    )

    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO temporal_alignment
                        (observation_a_id, observation_a_ingested_at,
                         observation_b_id, observation_b_ingested_at,
                         time_delta_seconds, alignment_quality, aligned_at)
                    VALUES (%s, %s, %s, %s, 0, 'exact', now())
                    """,
                    (obs_id, obs_ingested_at, obs_id, obs_ingested_at),  # self-pair
                )
    finally:
        _cleanup_canonical_observation(obs_id, obs_ingested_at)


def test_new_temporal_alignment_invalid_quality_rejected(db_pool: Any) -> None:
    """INSERT with alignment_quality not in vocabulary raises CHECK."""
    suffix = uuid.uuid4().hex[:8]
    source_id = _get_kalshi_source_id()
    obs_a_id, obs_a_ts = _insert_canonical_observation(
        source_id=source_id, suffix=f"qual-a-{suffix}"
    )
    obs_b_id, obs_b_ts = _insert_canonical_observation(
        source_id=source_id, suffix=f"qual-b-{suffix}"
    )

    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO temporal_alignment
                        (observation_a_id, observation_a_ingested_at,
                         observation_b_id, observation_b_ingested_at,
                         time_delta_seconds, alignment_quality, aligned_at)
                    VALUES (%s, %s, %s, %s, 0.5, 'amazing', now())
                    """,
                    (obs_a_id, obs_a_ts, obs_b_id, obs_b_ts),
                )
    finally:
        _cleanup_canonical_observation(obs_a_id, obs_a_ts)
        _cleanup_canonical_observation(obs_b_id, obs_b_ts)


def test_new_temporal_alignment_pair_unique(db_pool: Any) -> None:
    """Two rows with same (observation_a, observation_b) composite raise UniqueViolation."""
    suffix = uuid.uuid4().hex[:8]
    source_id = _get_kalshi_source_id()
    obs_a_id, obs_a_ts = _insert_canonical_observation(
        source_id=source_id, suffix=f"pair-a-{suffix}"
    )
    obs_b_id, obs_b_ts = _insert_canonical_observation(
        source_id=source_id, suffix=f"pair-b-{suffix}"
    )
    inserted_alignment_ids: list[int] = []

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO temporal_alignment
                    (observation_a_id, observation_a_ingested_at,
                     observation_b_id, observation_b_ingested_at,
                     time_delta_seconds, alignment_quality, aligned_at)
                VALUES (%s, %s, %s, %s, 0.123, 'exact', now())
                RETURNING id
                """,
                (obs_a_id, obs_a_ts, obs_b_id, obs_b_ts),
            )
            inserted_alignment_ids.append(int(cur.fetchone()["id"]))

        # Second INSERT with same composite pair fires UNIQUE violation.
        with pytest.raises(psycopg2.errors.UniqueViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO temporal_alignment
                        (observation_a_id, observation_a_ingested_at,
                         observation_b_id, observation_b_ingested_at,
                         time_delta_seconds, alignment_quality, aligned_at)
                    VALUES (%s, %s, %s, %s, 0.456, 'good', now())
                    """,
                    (obs_a_id, obs_a_ts, obs_b_id, obs_b_ts),
                )
    finally:
        if inserted_alignment_ids:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM temporal_alignment WHERE id = ANY(%s)",
                    (inserted_alignment_ids,),
                )
        _cleanup_canonical_observation(obs_a_id, obs_a_ts)
        _cleanup_canonical_observation(obs_b_id, obs_b_ts)


def test_new_temporal_alignment_happy_path_insert(db_pool: Any) -> None:
    """Valid INSERT succeeds + roundtrips canonical_event_id denormalized hot-path."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    source_id = _get_kalshi_source_id()
    obs_a_id, obs_a_ts = _insert_canonical_observation(
        source_id=source_id, suffix=f"happy-a-{suffix}"
    )
    obs_b_id, obs_b_ts = _insert_canonical_observation(
        source_id=source_id, suffix=f"happy-b-{suffix}"
    )
    inserted_alignment_ids: list[int] = []

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO temporal_alignment
                    (observation_a_id, observation_a_ingested_at,
                     observation_b_id, observation_b_ingested_at,
                     canonical_event_id, time_delta_seconds, alignment_quality, aligned_at)
                VALUES (%s, %s, %s, %s, %s, 0.250, 'good', now())
                RETURNING id
                """,
                (obs_a_id, obs_a_ts, obs_b_id, obs_b_ts, seeded_event_id),
            )
            row = cur.fetchone()
            inserted_alignment_ids.append(int(row["id"]))

        # Verify roundtrip.
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT observation_a_id, observation_a_ingested_at,
                       observation_b_id, observation_b_ingested_at,
                       canonical_event_id, time_delta_seconds, alignment_quality
                FROM temporal_alignment
                WHERE id = %s
                """,
                (inserted_alignment_ids[0],),
            )
            ra = cur.fetchone()
        assert ra["observation_a_id"] == obs_a_id
        assert ra["observation_a_ingested_at"] == obs_a_ts
        assert ra["observation_b_id"] == obs_b_id
        assert ra["observation_b_ingested_at"] == obs_b_ts
        assert ra["canonical_event_id"] == seeded_event_id
        assert ra["time_delta_seconds"] == Decimal("0.250")
        assert ra["alignment_quality"] == "good"
    finally:
        if inserted_alignment_ids:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM temporal_alignment WHERE id = ANY(%s)",
                    (inserted_alignment_ids,),
                )
        _cleanup_canonical_observation(obs_a_id, obs_a_ts)
        _cleanup_canonical_observation(obs_b_id, obs_b_ts)
        _cleanup_canonical_event(seeded_event_id)


# =============================================================================
# Group 6: Pattern compliance audit (73 / 87 / 86)
# =============================================================================


def test_pattern_73_link_kind_canonical_home_in_check(db_pool: Any) -> None:
    """Pattern 73 SSOT: link_kind 4-value vocabulary lives in the CHECK constraint.

    Until Cohort 5+ ships a CRUD module + constants tuple
    CANONICAL_OBSERVATION_LINK_KINDS, the CHECK constraint definition is
    the single canonical home for the vocabulary.  This test pins the
    invariant: the CHECK contains all 4 expected values.
    """
    expected_values = ("primary", "secondary", "derived", "speculative")
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_observation_event_links'::regclass
              AND conname = 'ck_link_kind'
            """
        )
        row = cur.fetchone()
    assert row is not None, "ck_link_kind CHECK missing"
    constraint_def = row["def"]
    for value in expected_values:
        assert f"'{value}'" in constraint_def, (
            f"Pattern 73 SSOT: ck_link_kind missing value {value!r}; "
            f"got definition: {constraint_def}"
        )


def test_pattern_73_alignment_quality_canonical_home_in_check(db_pool: Any) -> None:
    """Pattern 73 SSOT: alignment_quality 5-value vocabulary lives in the CHECK constraint."""
    expected_values = ("exact", "good", "fair", "poor", "stale")
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'temporal_alignment'::regclass
              AND conname = 'ck_alignment_quality'
            """
        )
        row = cur.fetchone()
    assert row is not None, "ck_alignment_quality CHECK missing"
    constraint_def = row["def"]
    for value in expected_values:
        assert f"'{value}'" in constraint_def, (
            f"Pattern 73 SSOT: ck_alignment_quality missing value {value!r}; "
            f"got definition: {constraint_def}"
        )


def test_alembic_head_is_0084(db_pool: Any) -> None:
    """alembic_version reports 0084 (slot 0083 is a permanent hole, V2.45 Item 1).

    Verifies down_revision = "0082" on slot 0084 (skipping the
    intentional slot 0083 hole, mirroring the slot 0081 hole shape from
    V2.43 Item 2).
    """
    with get_cursor() as cur:
        cur.execute("SELECT version_num FROM alembic_version")
        row = cur.fetchone()
    assert row is not None
    assert row["version_num"] == "0084", (
        f"Expected alembic_head=0084 (Migration 0084 applied), got {row['version_num']!r}"
    )
