"""Integration tests for Migration 0082 -- temporal_alignment canonical_event_id FK.

Verifies the POST-MIGRATION state of the single ALTER round shipped by
Migration 0082 (Cohort 4 slot 0082, ADR-118 V2.43 Item 2 + V2.42
sub-amendment B; build spec ``memory/build_spec_0082_pm_memo.md``):

    1. ``ALTER TABLE temporal_alignment ADD COLUMN canonical_event_id BIGINT``
       (nullable, no default) + FK to ``canonical_events(id) ON DELETE
       SET NULL`` (Pattern 84 NOT VALID + VALIDATE by analogy on populated
       table -- 2nd by-analogy use after slot 0080) +
       ``idx_temporal_alignment_canonical_event_id``.

Test groups (build spec § 5b):
    - TestColumnShape: BIGINT / nullable / no default.
    - TestForeignKeyConstraintShape: references canonical_events(id) +
      ON DELETE SET NULL.
    - TestForeignKeyValidity: FK reports convalidated=true in
      pg_constraint after the VALIDATE CONSTRAINT step.
    - TestIndexPresence: idx_temporal_alignment_canonical_event_id
      present + correct column.
    - TestSetNullSemantics: INSERT canonical_events row -> reference from
      temporal_alignment -> DELETE canonical_events row -> child FK
      column becomes NULL while child row survives.
    - TestForeignKeyViolationPropagation: INSERT child row with
      non-existent canonical_event_id -> ForeignKeyViolation (the
      VALIDATE step proved no orphans existed; FK enforcement on new
      writes is independent of NOT VALID).
    - TestNullAcceptance: INSERT with canonical_event_id=NULL succeeds
      (FK doesn't fire on NULL; column is nullable).
    - TestPopulationSafety: pre-existing rows have canonical_event_id IS
      NULL (DEFAULT-0 / accidental backfill check).  Slot 0082 inherits
      the slot 0080 reviewer-flagged amended formulation -- assert "no
      pre-existing row has a non-NULL value" rather than a true pre/post
      row-count comparison; the integration test layer can't reach
      pre-state because the migration ran at session start.
    - TestTemporalAlignmentWriterNonRegression: end-to-end writer
      scenario (happy-path alignment via _poll_once) succeeds with the
      new column present.  Writer doesn't reference canonical_event_id;
      nullable column with no default doesn't break writes.

Round-trip CI gate inheritance (PR #1081 / Epic #1071):
    Slot 0082's ``downgrade()`` is a pure inverse of ``upgrade()``;
    every CREATE has a matching DROP IF EXISTS in downgrade.  The
    round-trip CI gate auto-discovers slot 0082 on push and runs
    ``downgrade -> upgrade head`` against it.  No separate downgrade
    test is required here.

Issue: Epic #972 (Canonical Layer Foundation -- Phase B.5)
ADR: ADR-118 V2.43 Item 2 + V2.42 sub-amendment B
Build spec: ``memory/build_spec_0082_pm_memo.md``
Precedent: ``tests/integration/database/test_migration_0080_canonical_event_id_fks.py``

Markers:
    @pytest.mark.integration: real DB required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg2
import psycopg2.errors
import pytest

from precog.database.connection import get_cursor
from precog.schedulers.temporal_alignment_writer import (
    create_temporal_alignment_writer,
)

# V2.45 / Migration 0084: temporal_alignment was REDESIGNED as a pure-
# linkage table (DROP TABLE + CREATE TABLE with new shape).  Slot 0082's
# FK contribution + the slot-0035-era columns it sat atop are all GONE
# in the post-V2.45 schema.  Slot 0082 tests + temporal_alignment_writer
# are kept as institutional memory but skipped; the V2.45 redesign is
# tested by tests/integration/database/test_migration_0084_canonical_layer_redesign.py.
# See ADR-118 V2.45 Item 6 + memory/design_review_v246_input_memo.md.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skip(
        reason=(
            "V2.45 / Migration 0084 redesigned temporal_alignment as a pure-linkage "
            "table; slot 0082's FK on the old shape no longer exists.  See ADR-118 "
            "V2.45 Item 6 + test_migration_0084_canonical_layer_redesign.py for "
            "post-V2.45 coverage."
        )
    ),
]


# Shipped by slot 0082 -- (table, fk_constraint_name, index_name).
# Pattern 73 SSOT: the migration owns the names in code; this tuple
# mirrors verbatim.  Drift here => test fails => alignment forced.
_SLOT_0082_TARGET: tuple[str, str, str] = (
    "temporal_alignment",
    "fk_temporal_alignment_canonical_event_id",
    "idx_temporal_alignment_canonical_event_id",
)


# =============================================================================
# Seed helpers -- minimal-FK-chain seeders so the SET NULL cascade tests
# can DELETE the parent canonical_events row and observe the SET NULL
# behavior on temporal_alignment.
# =============================================================================


def _seed_canonical_event(suffix: str) -> int:
    """Seed a canonical_events row with no platform-tier FKs.

    Slot 0082 tests the REVERSE direction (temporal_alignment FK INTO
    canonical_events); the canonical row's own game_id / series_id are
    irrelevant here, so we leave them NULL and back the row with the
    seeded sports/game canonical_event_domains/types from migration 0067.

    Caller MUST pair with ``_cleanup_canonical_event(returned_id)`` in a
    finally block.
    """
    nk_hash = f"TEST-0082-evt-{suffix}".encode()
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
            (nk_hash, f"Slot 0082 test event ({suffix})"),
        )
        return int(cur.fetchone()["id"])


def _cleanup_canonical_event(canonical_event_id: int) -> None:
    """Best-effort delete of a canonical_events row."""
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_events WHERE id = %s",
                (canonical_event_id,),
            )
    except Exception:
        pass


def _seed_temporal_alignment_fk_chain(suffix: str) -> dict[str, int]:
    """Seed the FK parent chain temporal_alignment requires.

    temporal_alignment has FKs onto market_snapshots + game_states, both
    of which have their own FK chains: market_snapshots -> markets ->
    events -> games (+ platforms); game_states -> games (+ leagues).
    We seed a minimal chain and return the IDs needed for INSERTs into
    temporal_alignment.

    Caller MUST pair with ``_cleanup_temporal_alignment_fk_chain(returned_dict)``
    in a finally block.
    """
    suffix_short = suffix[:4]
    espn_event_id = f"TEST-0082-ESPN-{suffix}"
    team_home_code = f"82H{suffix_short[:7]}"
    team_away_code = f"82A{suffix_short[:7]}"

    with get_cursor(commit=True) as cur:
        cur.execute("SELECT id FROM sports WHERE sport_key = 'football'")
        sport_id = cur.fetchone()["id"]
        cur.execute("SELECT id FROM leagues WHERE league_key = 'nfl'")
        league_id = cur.fetchone()["id"]

        # Platform (idempotent).
        cur.execute(
            """
            INSERT INTO platforms (platform_id, platform_type, display_name, base_url, status)
            VALUES ('test_platform', 'trading', 'Test Platform', 'https://test.example.com', 'active')
            ON CONFLICT (platform_id) DO NOTHING
            """
        )

        # Game.
        cur.execute(
            """
            INSERT INTO games (
                sport, game_date, home_team_code, away_team_code, season,
                league, neutral_site, is_playoff, game_status, espn_event_id,
                data_source, sport_id, league_id, game_key
            )
            VALUES (
                'football', CURRENT_DATE, %s, %s, 2026,
                'nfl', FALSE, FALSE, 'scheduled', %s,
                'espn', %s, %s, %s
            )
            RETURNING id
            """,
            (
                team_home_code,
                team_away_code,
                espn_event_id,
                sport_id,
                league_id,
                f"GAME-TEST-0082-{suffix}",
            ),
        )
        game_id = int(cur.fetchone()["id"])

        # Event.
        cur.execute(
            """
            INSERT INTO events (
                platform_id, external_id, category, subcategory, title,
                status, game_id, event_key
            )
            VALUES ('test_platform', %s, 'sports', 'nfl', %s,
                    'scheduled', %s, %s)
            RETURNING id
            """,
            (
                f"TEST-0082-EVT-{suffix}",
                f"Test Event {suffix}",
                game_id,
                f"EVT-TEST-0082-{suffix}",
            ),
        )
        event_id = int(cur.fetchone()["id"])

        # Market.
        cur.execute(
            """
            INSERT INTO markets (
                platform_id, event_id, external_id, ticker, title,
                market_type, status, market_key
            )
            VALUES ('test_platform', %s, %s, %s, %s,
                    'binary', 'open', %s)
            RETURNING id
            """,
            (
                event_id,
                f"TEST-0082-EXT-{suffix}",
                f"TEST-0082-MKT-{suffix}",
                f"Test Market {suffix}",
                f"MKT-TEST-0082-{suffix}",
            ),
        )
        market_id = int(cur.fetchone()["id"])

        # Market snapshot.
        cur.execute(
            """
            INSERT INTO market_snapshots (
                market_id, yes_ask_price, no_ask_price, spread, volume,
                row_current_ind, row_start_ts
            )
            VALUES (%s, %s, %s, %s, %s, TRUE, NOW())
            RETURNING id
            """,
            (
                market_id,
                Decimal("0.5200"),
                Decimal("0.4800"),
                Decimal("0.0100"),
                100,
            ),
        )
        market_snapshot_id = int(cur.fetchone()["id"])

        # Game state (uses TEMP-{uuid} sentinel rewrite for game_state_key
        # per Migration 0062 partial UNIQUE index discipline).
        temp_key = f"TEMP-{uuid.uuid4()}"
        cur.execute(
            """
            INSERT INTO game_states (
                espn_event_id, home_score, away_score, period, game_status,
                league, league_id, data_source, game_id, game_state_key,
                row_current_ind, row_start_ts, neutral_site
            )
            VALUES (%s, 0, 0, 1, 'pre', 'nfl', %s, 'espn', %s, %s, TRUE, NOW(), FALSE)
            RETURNING id
            """,
            (espn_event_id, league_id, game_id, temp_key),
        )
        game_state_id = int(cur.fetchone()["id"])
        cur.execute(
            "UPDATE game_states SET game_state_key = %s WHERE id = %s",
            (f"GST-{game_state_id}", game_state_id),
        )

    return {
        "game_id": game_id,
        "event_id": event_id,
        "market_id": market_id,
        "market_snapshot_id": market_snapshot_id,
        "game_state_id": game_state_id,
    }


def _cleanup_temporal_alignment_fk_chain(ids: dict[str, int]) -> None:
    """Best-effort cleanup of the FK chain seeded by ``_seed_temporal_alignment_fk_chain``.

    Strict reverse FK order: children -> parents.
    """
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM temporal_alignment WHERE market_id = %s",
                (ids["market_id"],),
            )
            cur.execute("DELETE FROM market_snapshots WHERE id = %s", (ids["market_snapshot_id"],))
            cur.execute("DELETE FROM markets WHERE id = %s", (ids["market_id"],))
            cur.execute("DELETE FROM game_states WHERE id = %s", (ids["game_state_id"],))
            cur.execute("DELETE FROM events WHERE id = %s", (ids["event_id"],))
            cur.execute("DELETE FROM games WHERE id = %s", (ids["game_id"],))
    except Exception:
        pass


def _insert_temporal_alignment_row(
    *,
    market_id: int,
    market_snapshot_id: int,
    game_state_id: int,
    canonical_event_id: int | None = None,
) -> int:
    """Insert a temporal_alignment row, returning its id.

    Mirrors the writer's INSERT shape (the column list the writer
    actually uses in production); plus the new optional canonical_event_id.
    """
    now = datetime.now(tz=UTC)
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO temporal_alignment (
                market_id, market_snapshot_id, game_state_id,
                snapshot_time, game_state_time, time_delta_seconds,
                alignment_quality, canonical_event_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'good', %s)
            RETURNING id
            """,
            (
                market_id,
                market_snapshot_id,
                game_state_id,
                now,
                now - timedelta(seconds=5),
                Decimal("5"),
                canonical_event_id,
            ),
        )
        return int(cur.fetchone()["id"])


def _cleanup_temporal_alignment_row(temporal_alignment_id: int) -> None:
    """Best-effort delete of a temporal_alignment row."""
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM temporal_alignment WHERE id = %s",
                (temporal_alignment_id,),
            )
    except Exception:
        pass


# =============================================================================
# Group 1: Column shape (BIGINT / nullable / no default).
# =============================================================================


def test_canonical_event_id_column_shape(db_pool: Any) -> None:
    """``temporal_alignment.canonical_event_id`` exists as BIGINT / nullable / no default.

    Build spec § 5b "Column shape": the post-migration column exists
    with the exact shape -- BIGINT (matches canonical_events.id BIGSERIAL
    surrogate type), nullable=YES (backfill deferred to Cohort 5+; new
    rows write NULL until the matcher binds them), no default (matcher
    explicit-binds; we don't want silent default=0 or similar).
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'temporal_alignment'
              AND column_name = 'canonical_event_id'
            """
        )
        row = cur.fetchone()
    assert row is not None, (
        "temporal_alignment.canonical_event_id column must exist post-Migration-0082"
    )
    assert row["data_type"] == "bigint", (
        f"temporal_alignment.canonical_event_id must be bigint; got {row['data_type']!r}"
    )
    assert row["is_nullable"] == "YES", (
        "temporal_alignment.canonical_event_id must be nullable; "
        f"got is_nullable={row['is_nullable']!r}"
    )
    assert row["column_default"] is None, (
        "temporal_alignment.canonical_event_id must have no default; "
        f"got column_default={row['column_default']!r}"
    )


# =============================================================================
# Group 2: FK constraint shape (REFERENCES canonical_events(id) + ON DELETE SET NULL).
# =============================================================================


def test_fk_renders_with_set_null_action(db_pool: Any) -> None:
    """``pg_get_constraintdef`` emits ``ON DELETE SET NULL`` for the new FK.

    Positive assertion (mirrors slot 0080 group 1): asserts the SET NULL
    clause is PRESENT in the constraint definition rather than asserting
    absence-of-other-clauses.  Belt-and-suspenders: confirm the FK
    references the expected parent table + column to catch a future
    migration that re-points the FK while keeping the constraint name.
    """
    table_name, constraint_name, _index_name = _SLOT_0082_TARGET
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = %s::regclass
              AND conname = %s
            """,
            (table_name, constraint_name),
        )
        row = cur.fetchone()
    assert row is not None, f"{constraint_name} must exist on {table_name} post-Migration-0082"
    fk_def = row["def"]
    assert "ON DELETE SET NULL" in fk_def, (
        f"{constraint_name} must include 'ON DELETE SET NULL' post-Migration-0082; got: {fk_def}"
    )
    assert "REFERENCES canonical_events(id)" in fk_def, (
        f"{constraint_name} must REFERENCE canonical_events(id); got: {fk_def}"
    )
    assert "FOREIGN KEY (canonical_event_id)" in fk_def, (
        f"{constraint_name} must be FOREIGN KEY (canonical_event_id); got: {fk_def}"
    )


# =============================================================================
# Group 3: FK validity (convalidated=true post-VALIDATE CONSTRAINT step).
# =============================================================================


def test_fk_is_validated(db_pool: Any) -> None:
    """The FK reports ``convalidated=true`` in pg_constraint.

    Build spec § 5b "FK validity (post-VALIDATE)": the migration ships a
    VALIDATE CONSTRAINT step after the ADD CONSTRAINT NOT VALID.  This
    test asserts the validation actually ran -- a half-validated state
    (NOT VALID flag still set) would surface as ``convalidated=false``.

    Pattern 84 application-by-analogy on FKs: the operational benefit of
    NOT VALID + VALIDATE is to defer the lock-heavy scan; the safety
    requirement is that VALIDATE actually runs.  This test enforces the
    second half of the pattern.
    """
    table_name, constraint_name, _index_name = _SLOT_0082_TARGET
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT convalidated
            FROM pg_constraint
            WHERE conrelid = %s::regclass
              AND conname = %s
            """,
            (table_name, constraint_name),
        )
        row = cur.fetchone()
    assert row is not None, f"{constraint_name} must exist on {table_name} post-Migration-0082"
    assert row["convalidated"] is True, (
        f"{constraint_name} must be convalidated=true post-Migration-0082 "
        f"(VALIDATE CONSTRAINT step must run); got convalidated={row['convalidated']!r}"
    )


# =============================================================================
# Group 4: Index presence (idx_temporal_alignment_canonical_event_id).
# =============================================================================


def test_index_present_with_correct_column(db_pool: Any) -> None:
    """``idx_temporal_alignment_canonical_event_id`` is present and indexes the FK column.

    Build spec § 5b "Index presence": the matcher's reverse-lookup
    ("which temporal_alignment rows are bound to canonical event X?") and
    the FK's ON DELETE SET NULL cascade fan-out both depend on this
    index.  Without it, every parent DELETE forces a sequential scan
    on the child table.

    Asserts on indexdef column-list rather than indexname substring per
    feedback_pg_partition_index_name_truncation.md (PG truncates index
    names at 63 bytes for partitions; not a concern here since
    temporal_alignment is non-partitioned, but the discipline of asserting
    on column-list is the more robust idiom regardless).
    """
    table_name, _constraint_name, index_name = _SLOT_0082_TARGET
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE tablename = %s AND indexname = %s
            """,
            (table_name, index_name),
        )
        row = cur.fetchone()
    assert row is not None, f"{index_name} must exist on {table_name} post-Migration-0082"
    indexdef = row["indexdef"]
    # Robust assertion on the indexed column rather than the full index
    # DDL string -- different PG versions can emit slightly different
    # whitespace / USING clauses.
    assert "(canonical_event_id)" in indexdef, (
        f"{index_name} must index column canonical_event_id; got: {indexdef}"
    )


# =============================================================================
# Group 5: SET NULL semantics -- DELETE canonical_events, expect child
# row survives with canonical_event_id=NULL.
# =============================================================================


def test_temporal_alignment_canonical_event_id_set_null_on_canonical_events_delete(
    db_pool: Any,
) -> None:
    """DELETE canonical_events row cascades temporal_alignment.canonical_event_id to NULL.

    End-to-end behavioral evidence that slot 0082's SET NULL polarity
    actually fires under the canonical-outlives-platform contract.

    Sequence:
        1. Seed a canonical_events row + a temporal_alignment FK chain.
        2. Insert a temporal_alignment row pointing at the canonical event.
        3. DELETE the canonical_events row.
        4. Assert the temporal_alignment row still exists.
        5. Assert temporal_alignment.canonical_event_id is NULL.
    """
    suffix = uuid.uuid4().hex[:8]
    canonical_event_id: int | None = None
    fk_chain_ids: dict[str, int] | None = None
    temporal_alignment_id: int | None = None
    try:
        canonical_event_id = _seed_canonical_event(suffix)
        fk_chain_ids = _seed_temporal_alignment_fk_chain(suffix)
        temporal_alignment_id = _insert_temporal_alignment_row(
            market_id=fk_chain_ids["market_id"],
            market_snapshot_id=fk_chain_ids["market_snapshot_id"],
            game_state_id=fk_chain_ids["game_state_id"],
            canonical_event_id=canonical_event_id,
        )

        # Pre-condition: the temporal_alignment row links the canonical event.
        with get_cursor() as cur:
            cur.execute(
                "SELECT canonical_event_id FROM temporal_alignment WHERE id = %s",
                (temporal_alignment_id,),
            )
            pre_row = cur.fetchone()
        assert pre_row is not None
        assert pre_row["canonical_event_id"] == canonical_event_id, (
            "temporal_alignment.canonical_event_id must reference the seeded "
            "canonical_event pre-DELETE"
        )

        # Trigger the SET NULL cascade.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_events WHERE id = %s",
                (canonical_event_id,),
            )
        # The canonical_events row no longer exists -- skip cleanup.
        canonical_event_id = None

        # Post-condition: temporal_alignment row survives with canonical_event_id NULL.
        with get_cursor() as cur:
            cur.execute(
                "SELECT canonical_event_id FROM temporal_alignment WHERE id = %s",
                (temporal_alignment_id,),
            )
            post_row = cur.fetchone()
        assert post_row is not None, (
            "temporal_alignment row must survive DELETE FROM canonical_events "
            "(SET NULL preserves the platform-tier row per ADR-118 V2.42 "
            "sub-amendment B canonical-outlives-platform polarity)"
        )
        assert post_row["canonical_event_id"] is None, (
            f"temporal_alignment.canonical_event_id must be NULL post-DELETE-FROM-canonical_events; "
            f"got {post_row['canonical_event_id']!r}"
        )
    finally:
        if temporal_alignment_id is not None:
            _cleanup_temporal_alignment_row(temporal_alignment_id)
        if fk_chain_ids is not None:
            _cleanup_temporal_alignment_fk_chain(fk_chain_ids)
        if canonical_event_id is not None:
            _cleanup_canonical_event(canonical_event_id)


# =============================================================================
# Group 6: FK violation propagation -- INSERT child with non-existent
# canonical_event_id raises ForeignKeyViolation.
# =============================================================================


def test_temporal_alignment_fk_violation_on_nonexistent_canonical_event(
    db_pool: Any,
) -> None:
    """INSERT temporal_alignment with non-existent canonical_event_id raises FK violation.

    The VALIDATE CONSTRAINT step proved no orphans existed at migration
    time; THIS test asserts FK enforcement on NEW writes.  The two
    properties are independent: NOT VALID briefly suspends scan-of-existing-
    rows enforcement, but always-on enforcement of NEW writes is part of
    the constraint definition itself.

    Uses an absurdly large id (2^31-1) that cannot collide with an actual
    canonical_events.id (BIGSERIAL starts at 1, dev DB has at most a few
    canonical_events rows).
    """
    nonexistent_id = 2_147_483_647  # close to INT_MAX, far from any real id
    suffix = uuid.uuid4().hex[:8]
    fk_chain_ids: dict[str, int] | None = None
    try:
        fk_chain_ids = _seed_temporal_alignment_fk_chain(suffix)
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            _insert_temporal_alignment_row(
                market_id=fk_chain_ids["market_id"],
                market_snapshot_id=fk_chain_ids["market_snapshot_id"],
                game_state_id=fk_chain_ids["game_state_id"],
                canonical_event_id=nonexistent_id,
            )
    finally:
        if fk_chain_ids is not None:
            _cleanup_temporal_alignment_fk_chain(fk_chain_ids)


# =============================================================================
# Group 7: NULL acceptance -- INSERT with canonical_event_id=NULL succeeds
# (column nullable, FK doesn't fire on NULL).
# =============================================================================


def test_temporal_alignment_accepts_null_canonical_event_id(db_pool: Any) -> None:
    """INSERT temporal_alignment with canonical_event_id=NULL succeeds.

    The column is nullable (build spec § 2: backfill deferred); existing
    rows are NULL until the matcher binds them.  This test asserts the
    nullable-FK contract: NULL is a legal value, FK doesn't fire on
    NULL per SQL standard semantics.
    """
    suffix = uuid.uuid4().hex[:8]
    fk_chain_ids: dict[str, int] | None = None
    temporal_alignment_id: int | None = None
    try:
        fk_chain_ids = _seed_temporal_alignment_fk_chain(suffix)
        temporal_alignment_id = _insert_temporal_alignment_row(
            market_id=fk_chain_ids["market_id"],
            market_snapshot_id=fk_chain_ids["market_snapshot_id"],
            game_state_id=fk_chain_ids["game_state_id"],
            canonical_event_id=None,
        )
        with get_cursor() as cur:
            cur.execute(
                "SELECT canonical_event_id FROM temporal_alignment WHERE id = %s",
                (temporal_alignment_id,),
            )
            row = cur.fetchone()
        assert row is not None, "temporal_alignment row must exist post-INSERT"
        assert row["canonical_event_id"] is None, (
            "temporal_alignment.canonical_event_id must be NULL when explicitly set NULL; "
            f"got {row['canonical_event_id']!r}"
        )
    finally:
        if temporal_alignment_id is not None:
            _cleanup_temporal_alignment_row(temporal_alignment_id)
        if fk_chain_ids is not None:
            _cleanup_temporal_alignment_fk_chain(fk_chain_ids)


# =============================================================================
# Group 8: Population-safety surface -- the migration only ADDs schema;
# pre-existing rows are unaffected.
#
# Slot 0082 inherits the slot 0080 reviewer-flagged amended formulation:
# assert "no pre-existing row has a non-NULL canonical_event_id" rather
# than a true pre/post row-count comparison; the integration test layer
# can't reach pre-state because the migration ran at session start.
# =============================================================================


def test_existing_rows_have_null_canonical_event_id(db_pool: Any) -> None:
    """Every pre-existing row has canonical_event_id=NULL post-migration.

    Slot 0082 ships ADD COLUMN with no DEFAULT clause.  PG semantics:
    no DEFAULT + nullable column => existing rows get NULL.  This test
    asserts the shape-level invariant by counting non-NULL values that
    were NOT inserted by THIS test run.

    NOTE: tests in this file insert rows linked to a per-test FK chain
    via ``_seed_temporal_alignment_fk_chain`` (market_id +
    market_snapshot_id + game_state_id all unique per test).  We exclude
    those via ``market_id NOT IN (SELECT id FROM markets WHERE
    market_key LIKE 'MKT-TEST-0082-%')`` -- the test-row exclusion uses
    the per-test market business-key prefix.

    The COUNT(*) WHERE canonical_event_id IS NOT NULL form catches the
    pathological "DEFAULT 0" or "DEFAULT some-real-id" migration bug
    that would otherwise pass column-shape inspection.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT count(*) AS non_null_count
            FROM temporal_alignment ta
            WHERE ta.canonical_event_id IS NOT NULL
              AND ta.market_id NOT IN (
                  SELECT id FROM markets
                  WHERE market_key LIKE 'MKT-TEST-0082-%%'
              )
            """
        )
        row = cur.fetchone()
    assert row is not None
    assert row["non_null_count"] == 0, (
        "temporal_alignment must have 0 non-NULL canonical_event_id values from "
        "pre-existing rows post-Migration-0082 (slot 0082 ADD COLUMN with no "
        f"DEFAULT => existing rows get NULL); got {row['non_null_count']!r}"
    )


# =============================================================================
# Group 9: temporal_alignment_writer non-regression -- end-to-end writer
# scenario succeeds with the new column present.  Writer doesn't reference
# canonical_event_id; nullable column with no default doesn't break writes.
# =============================================================================


def test_temporal_alignment_writer_non_regression(db_pool: Any) -> None:
    """Writer's _poll_once still produces alignment rows post-Migration-0082.

    The existing ``temporal_alignment_writer`` does NOT reference the new
    ``canonical_event_id`` column.  Adding a nullable column with no
    default to a table is a back-compatible schema change: existing
    INSERT statements that don't list the new column succeed (the column
    gets NULL by PG semantics).

    This test exercises the actual writer's _poll_once method on a
    seeded FK chain that produces exactly one unaligned (market_snapshot,
    game_state) pair.  Pass criterion: the writer creates a
    temporal_alignment row for that pair, with canonical_event_id IS
    NULL (writer doesn't touch the new column; existing rows + writer-
    inserted rows are NULL until Cohort 5+ matcher backfills).

    Mirrors the
    ``test_happy_path_alignment_produces_good_quality`` shape from
    ``tests/integration/schedulers/test_temporal_alignment_writer_integration.py``
    -- minimal copy of the writer fixture pattern, narrowed to the
    one-pair / one-alignment scenario sufficient for non-regression.
    """
    suffix = uuid.uuid4().hex[:8]
    fk_chain_ids: dict[str, int] | None = None
    try:
        # Re-seed the FK chain but with row_start_ts in the recent past
        # so the writer's lookback window picks the pair up.  The shared
        # _seed_temporal_alignment_fk_chain stamps NOW(); we need a
        # tighter delta to get a 'good' or better quality classification.
        # Re-seed inline rather than parametrize the shared helper to
        # keep the helper API simple.
        suffix_short = suffix[:4]
        espn_event_id = f"TEST-0082-NR-ESPN-{suffix}"
        team_home_code = f"82H{suffix_short[:7]}"
        team_away_code = f"82A{suffix_short[:7]}"
        now = datetime.now(tz=UTC)

        with get_cursor(commit=True) as cur:
            cur.execute("SELECT id FROM sports WHERE sport_key = 'football'")
            sport_id = cur.fetchone()["id"]
            cur.execute("SELECT id FROM leagues WHERE league_key = 'nfl'")
            league_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO platforms (
                    platform_id, platform_type, display_name, base_url, status
                )
                VALUES (
                    'test_platform', 'trading', 'Test Platform',
                    'https://test.example.com', 'active'
                )
                ON CONFLICT (platform_id) DO NOTHING
                """
            )

            cur.execute(
                """
                INSERT INTO games (
                    sport, game_date, home_team_code, away_team_code, season,
                    league, neutral_site, is_playoff, game_status,
                    espn_event_id, data_source, sport_id, league_id, game_key
                )
                VALUES (
                    'football', CURRENT_DATE, %s, %s, 2026,
                    'nfl', FALSE, FALSE, 'scheduled',
                    %s, 'espn', %s, %s, %s
                )
                RETURNING id
                """,
                (
                    team_home_code,
                    team_away_code,
                    espn_event_id,
                    sport_id,
                    league_id,
                    f"GAME-TEST-0082-NR-{suffix}",
                ),
            )
            game_id = int(cur.fetchone()["id"])

            cur.execute(
                """
                INSERT INTO events (
                    platform_id, external_id, category, subcategory, title,
                    status, game_id, event_key
                )
                VALUES (
                    'test_platform', %s, 'sports', 'nfl', %s,
                    'scheduled', %s, %s
                )
                RETURNING id
                """,
                (
                    f"TEST-0082-NR-EVT-{suffix}",
                    f"Test Event NR {suffix}",
                    game_id,
                    f"EVT-TEST-0082-NR-{suffix}",
                ),
            )
            event_id = int(cur.fetchone()["id"])

            cur.execute(
                """
                INSERT INTO markets (
                    platform_id, event_id, external_id, ticker, title,
                    market_type, status, market_key
                )
                VALUES (
                    'test_platform', %s, %s, %s, %s,
                    'binary', 'open', %s
                )
                RETURNING id
                """,
                (
                    event_id,
                    f"TEST-0082-NR-EXT-{suffix}",
                    f"TEST-0082-NR-MKT-{suffix}",
                    f"Test Market NR {suffix}",
                    f"MKT-TEST-0082-NR-{suffix}",
                ),
            )
            market_id = int(cur.fetchone()["id"])

            # Snapshot at -60s; game state at -55s -- ~5s delta -> 'good'.
            cur.execute(
                """
                INSERT INTO market_snapshots (
                    market_id, yes_ask_price, no_ask_price, spread, volume,
                    row_current_ind, row_start_ts
                )
                VALUES (%s, %s, %s, %s, %s, TRUE, %s)
                RETURNING id
                """,
                (
                    market_id,
                    Decimal("0.5200"),
                    Decimal("0.4800"),
                    Decimal("0.0100"),
                    100,
                    now - timedelta(seconds=60),
                ),
            )
            ms_id = int(cur.fetchone()["id"])

            temp_key = f"TEMP-{uuid.uuid4()}"
            cur.execute(
                """
                INSERT INTO game_states (
                    espn_event_id, home_score, away_score, period, game_status,
                    league, league_id, data_source, game_id, game_state_key,
                    row_current_ind, row_start_ts, neutral_site
                )
                VALUES (%s, 7, 3, 1, 'in_progress', 'nfl', %s, 'espn', %s, %s, TRUE, %s, FALSE)
                RETURNING id
                """,
                (
                    espn_event_id,
                    league_id,
                    game_id,
                    temp_key,
                    now - timedelta(seconds=55),
                ),
            )
            gs_id = int(cur.fetchone()["id"])
            cur.execute(
                "UPDATE game_states SET game_state_key = %s WHERE id = %s",
                (f"GST-{gs_id}", gs_id),
            )

        fk_chain_ids = {
            "game_id": game_id,
            "event_id": event_id,
            "market_id": market_id,
            "market_snapshot_id": ms_id,
            "game_state_id": gs_id,
        }

        # Run the writer.  Under xdist we cannot assert on the global
        # items_created counter; assert only on rows produced for THIS
        # test's market_id (unique per test).
        writer = create_temporal_alignment_writer(
            poll_interval=30,
            lookback_seconds=600,
            batch_limit=1000,
        )
        writer._poll_once()

        with get_cursor() as cur:
            cur.execute(
                """
                SELECT alignment_quality, time_delta_seconds, canonical_event_id
                FROM temporal_alignment
                WHERE market_snapshot_id = %s AND game_state_id = %s
                """,
                (ms_id, gs_id),
            )
            rows = cur.fetchall()

        assert len(rows) == 1, (
            "writer must produce exactly one alignment row for the seeded "
            f"(market_snapshot, game_state) pair; got {len(rows)} rows"
        )
        # Writer is non-regression-clean: the new column doesn't break
        # the writer's INSERT.  The 5s delta classifies as 'good'
        # (1 < d <= 15 per writer's quality threshold table).
        assert rows[0]["alignment_quality"] == "good", (
            f"5s delta must classify as 'good'; got {rows[0]['alignment_quality']!r}"
        )
        assert Decimal("1") < rows[0]["time_delta_seconds"] <= Decimal("15"), (
            f"5s delta must fall inside good tier (1, 15]; got {rows[0]['time_delta_seconds']!r}"
        )
        # Writer doesn't reference canonical_event_id; the new column
        # gets NULL on writer-inserted rows until the matcher (Cohort 5+)
        # ships.  This is the load-bearing non-regression assertion --
        # if the writer somehow started binding canonical_event_id
        # (drift / accidental change), this would surface.
        assert rows[0]["canonical_event_id"] is None, (
            "writer must NOT populate canonical_event_id (no matcher "
            f"yet; Cohort 5+ work); got {rows[0]['canonical_event_id']!r}"
        )
    finally:
        if fk_chain_ids is not None:
            _cleanup_temporal_alignment_fk_chain(fk_chain_ids)
