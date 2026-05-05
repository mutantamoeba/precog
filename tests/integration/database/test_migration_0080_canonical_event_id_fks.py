"""Integration tests for Migration 0080 -- game_states + games canonical_event_id FKs.

Verifies the POST-MIGRATION state of the two structurally-identical
ALTER rounds shipped by Migration 0080 (Cohort 4 slot 0080, ADR-118
V2.43 Item 2 + V2.42 sub-amendment B; build spec
``memory/build_spec_0080_pm_memo.md``):

    1. ``ALTER TABLE game_states ADD COLUMN canonical_event_id BIGINT``
       (nullable, no default) + FK to ``canonical_events(id) ON DELETE
       SET NULL`` (Pattern 84 NOT VALID + VALIDATE by analogy on populated
       table) + ``idx_game_states_canonical_event_id``.
    2. Same shape on ``games``: column + FK + index.

Test groups (build spec § 5b):
    - TestColumnShape: BIGINT / nullable / no default on both tables.
    - TestForeignKeyConstraintShape: references canonical_events(id) +
      ON DELETE SET NULL on both tables.
    - TestForeignKeyValidity: both FKs report convalidated=true in
      pg_constraint after the VALIDATE CONSTRAINT step.
    - TestIndexPresence: idx_<table>_canonical_event_id present + correct
      column on both tables.
    - TestSetNullSemantics: INSERT canonical_events row -> reference from
      game_states/games -> DELETE canonical_events row -> child FK column
      becomes NULL while child row survives.
    - TestForeignKeyViolationPropagation: INSERT child row with
      non-existent canonical_event_id -> ForeignKeyViolation (the
      VALIDATE step proved no orphans existed; FK enforcement on new
      writes is independent of NOT VALID).
    - TestNullAcceptance: INSERT with canonical_event_id=NULL succeeds
      on both tables (FK doesn't fire on NULL; column is nullable).
    - TestPopulationSafety: row counts on game_states + games
      pre-vs-post migration are identical (the migration only ADDs
      schema; no INSERT/UPDATE/DELETE on data rows).  This is exercised
      indirectly here -- if any pre-existing row violated the FK shape,
      the VALIDATE step would have failed at migration time.  The
      population-safety surface is tested at deploy time AND by the
      round-trip CI gate (PR #1081 / Epic #1071) which verifies
      schema-level reversibility round-trip-clean.

Round-trip CI gate inheritance (PR #1081 / Epic #1071):
    Slot 0080's ``downgrade()`` is a pure inverse of ``upgrade()``;
    every CREATE has a matching DROP IF EXISTS in downgrade.  The
    round-trip CI gate auto-discovers slot 0080 on push and runs
    ``downgrade -> upgrade head`` against it.  No separate downgrade
    test is required here.

Issue: Epic #972 (Canonical Layer Foundation -- Phase B.5)
ADR: ADR-118 V2.43 Item 2 + V2.42 sub-amendment B
Build spec: ``memory/build_spec_0080_pm_memo.md``

Markers:
    @pytest.mark.integration: real DB required.
"""

import uuid
from typing import Any

import psycopg2
import psycopg2.errors
import pytest

from precog.database.connection import get_cursor

pytestmark = [pytest.mark.integration]


# Shipped by slot 0080 -- (table, fk_constraint_name, index_name).
# Pattern 73 SSOT: the migration owns the names in code; this tuple
# mirrors verbatim.  Drift here => test fails => alignment forced.
_SLOT_0080_RETROFITTED: tuple[tuple[str, str, str], ...] = (
    ("game_states", "fk_game_states_canonical_event_id", "idx_game_states_canonical_event_id"),
    ("games", "fk_games_canonical_event_id", "idx_games_canonical_event_id"),
)


# =============================================================================
# Seed helpers -- minimal-FK-chain platform-tier rows so the SET NULL
# cascade tests can DELETE the parent canonical_events row and observe
# the SET NULL behavior on game_states / games.
# =============================================================================


def _seed_canonical_event(suffix: str) -> int:
    """Seed a canonical_events row with no platform-tier FKs.

    Slot 0080 tests the REVERSE direction (platform table FK INTO
    canonical_events); the canonical row's own game_id / series_id are
    irrelevant here, so we leave them NULL and back the row with the
    seeded sports/game canonical_event_domains/types from migration 0067.

    Caller MUST pair with ``_cleanup_canonical_event(returned_id)`` in a
    finally block.
    """
    nk_hash = f"TEST-0080-evt-{suffix}".encode()
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
            (nk_hash, f"Slot 0080 test event ({suffix})"),
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


def _seed_game(suffix: str, *, canonical_event_id: int | None = None) -> int:
    """Seed a games row with optional canonical_event_id binding.

    Uses NULL home_team_id / away_team_id / venue_id (all nullable) so
    the test does not need to seed teams + venues.  Pairs with
    ``_cleanup_game(returned_id)`` in a finally block.

    Team codes truncate to 10 chars; keep slot-tag + H/A differentiator
    FIRST so the suffix entropy survives -- the naive
    ``f"TEST-0080-HOME-{suffix}"[:10]`` form yields ``"TEST-0080-"`` for
    both home + away (suffix dropped), which would collide under
    pytest-xdist multi-worker runs of this test on the same game_date
    (CURRENT_DATE) -- ``uq_games_matchup`` violates.  Pattern lifted
    from test_migration_0077_*.py session-83 lesson.
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO games (
                sport, game_date, home_team_code, away_team_code, season,
                league, neutral_site, is_playoff, game_status,
                data_source, sport_id, league_id, game_key,
                canonical_event_id
            )
            VALUES (
                'football', CURRENT_DATE, %s, %s, 2026,
                'nfl', FALSE, FALSE, 'scheduled',
                'espn',
                (SELECT id FROM sports WHERE sport_key = 'football'),
                (SELECT id FROM leagues WHERE league_key = 'nfl'),
                %s, %s
            )
            RETURNING id
            """,
            (
                f"80H{suffix[:7]}",
                f"80A{suffix[:7]}",
                f"GAME-TEST-0080-{suffix}",
                canonical_event_id,
            ),
        )
        return int(cur.fetchone()["id"])


def _cleanup_game(game_id: int) -> None:
    """Best-effort delete of a games row seeded by ``_seed_game``."""
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM games WHERE id = %s", (game_id,))
    except Exception:
        pass


def _seed_game_state(
    suffix: str,
    *,
    canonical_event_id: int | None = None,
    game_id: int | None = None,
) -> int:
    """Seed a game_states row with optional canonical_event_id binding.

    Requires ``espn_event_id`` (NOT NULL), ``game_state_key`` (NOT NULL),
    and ``league_id`` (NOT NULL).  Uses unique-per-suffix values so
    repeated runs + xdist parallelism don't collide on the
    ``idx_game_states_current_unique`` partial index (espn_event_id WHERE
    row_current_ind=true).
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO game_states (
                espn_event_id, game_state_key, league, league_id,
                game_status, data_source, canonical_event_id, game_id
            )
            VALUES (
                %s, %s, 'nfl',
                (SELECT id FROM leagues WHERE league_key = 'nfl'),
                'pre', 'espn', %s, %s
            )
            RETURNING id
            """,
            (
                f"TEST-0080-ESPN-{suffix}",
                f"TEST-0080-GSK-{suffix}",
                canonical_event_id,
                game_id,
            ),
        )
        return int(cur.fetchone()["id"])


def _cleanup_game_state(game_state_id: int) -> None:
    """Best-effort delete of a game_states row seeded by ``_seed_game_state``."""
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM game_states WHERE id = %s", (game_state_id,))
    except Exception:
        pass


# =============================================================================
# Group 1: Column shape (BIGINT / nullable / no default on both tables).
# =============================================================================


@pytest.mark.parametrize(
    "table_name",
    ["game_states", "games"],
)
def test_canonical_event_id_column_shape(db_pool: Any, table_name: str) -> None:
    """``canonical_event_id`` exists on both tables as BIGINT / nullable / no default.

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
            WHERE table_name = %s AND column_name = 'canonical_event_id'
            """,
            (table_name,),
        )
        row = cur.fetchone()
    assert row is not None, f"{table_name}.canonical_event_id column must exist post-Migration-0080"
    assert row["data_type"] == "bigint", (
        f"{table_name}.canonical_event_id must be bigint; got {row['data_type']!r}"
    )
    assert row["is_nullable"] == "YES", (
        f"{table_name}.canonical_event_id must be nullable; got is_nullable={row['is_nullable']!r}"
    )
    assert row["column_default"] is None, (
        f"{table_name}.canonical_event_id must have no default; "
        f"got column_default={row['column_default']!r}"
    )


# =============================================================================
# Group 2: FK constraint shape (REFERENCES canonical_events(id) + ON DELETE SET NULL).
# =============================================================================


@pytest.mark.parametrize(
    ("table_name", "constraint_name", "_index_name"),
    _SLOT_0080_RETROFITTED,
)
def test_fk_renders_with_set_null_action(
    db_pool: Any,
    table_name: str,
    constraint_name: str,
    _index_name: str,
) -> None:
    """``pg_get_constraintdef`` emits ``ON DELETE SET NULL`` for both new FKs.

    Positive assertion (mirrors test_migration_0077 group 1): asserts the
    SET NULL clause is PRESENT in the constraint definition rather than
    asserting absence-of-other-clauses.  Belt-and-suspenders: confirm
    the FK references the expected parent table + column to catch a
    future migration that re-points the FK while keeping the constraint
    name.
    """
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
    assert row is not None, f"{constraint_name} must exist on {table_name} post-Migration-0080"
    fk_def = row["def"]
    assert "ON DELETE SET NULL" in fk_def, (
        f"{constraint_name} must include 'ON DELETE SET NULL' post-Migration-0080; got: {fk_def}"
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


@pytest.mark.parametrize(
    ("table_name", "constraint_name", "_index_name"),
    _SLOT_0080_RETROFITTED,
)
def test_fk_is_validated(
    db_pool: Any,
    table_name: str,
    constraint_name: str,
    _index_name: str,
) -> None:
    """Both FKs report ``convalidated=true`` in pg_constraint.

    Build spec § 5b "FK validity (post-VALIDATE)": the migration ships a
    VALIDATE CONSTRAINT step after each ADD CONSTRAINT NOT VALID.  This
    test asserts the validation actually ran -- a half-validated state
    (NOT VALID flag still set) would surface as ``convalidated=false``.

    Pattern 84 application-by-analogy on FKs: the operational benefit of
    NOT VALID + VALIDATE is to defer the lock-heavy scan; the safety
    requirement is that VALIDATE actually runs.  This test enforces the
    second half of the pattern.
    """
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
    assert row is not None, f"{constraint_name} must exist on {table_name} post-Migration-0080"
    assert row["convalidated"] is True, (
        f"{constraint_name} must be convalidated=true post-Migration-0080 "
        f"(VALIDATE CONSTRAINT step must run); got convalidated={row['convalidated']!r}"
    )


# =============================================================================
# Group 4: Index presence (idx_<table>_canonical_event_id on both tables).
# =============================================================================


@pytest.mark.parametrize(
    ("table_name", "_constraint_name", "index_name"),
    _SLOT_0080_RETROFITTED,
)
def test_index_present_with_correct_column(
    db_pool: Any,
    table_name: str,
    _constraint_name: str,
    index_name: str,
) -> None:
    """``idx_<table>_canonical_event_id`` is present and indexes the FK column.

    Build spec § 5b "Index presence": the matcher's reverse-lookup
    ("which platform-tier rows are bound to canonical event X?") and
    the FK's ON DELETE SET NULL cascade fan-out both depend on this
    index.  Without it, every parent DELETE forces a sequential scan
    on the child table.

    Asserts on indexdef column-list rather than indexname substring per
    feedback_pg_partition_index_name_truncation.md (PG truncates index
    names at 63 bytes for partitions; not a concern here since these
    are non-partitioned tables, but the discipline of asserting on
    column-list is the more robust idiom regardless).
    """
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
    assert row is not None, f"{index_name} must exist on {table_name} post-Migration-0080"
    indexdef = row["indexdef"]
    # Robust assertion on the indexed column rather than the full
    # index DDL string -- different PG versions can emit slightly
    # different whitespace / USING clauses.
    assert "(canonical_event_id)" in indexdef, (
        f"{index_name} must index column canonical_event_id; got: {indexdef}"
    )


# =============================================================================
# Group 5: SET NULL semantics -- DELETE canonical_events, expect child
# rows survive with canonical_event_id=NULL.
# =============================================================================


def test_game_states_canonical_event_id_set_null_on_canonical_events_delete(
    db_pool: Any,
) -> None:
    """DELETE canonical_events row cascades game_states.canonical_event_id to NULL.

    End-to-end behavioral evidence that slot 0080's SET NULL polarity
    actually fires under the canonical-outlives-platform contract.

    Sequence:
        1. Seed a canonical_events row.
        2. Seed a game_states row with canonical_event_id pointing at it.
        3. DELETE the canonical_events row.
        4. Assert the game_states row still exists.
        5. Assert game_states.canonical_event_id is NULL.
    """
    suffix = uuid.uuid4().hex[:8]
    canonical_event_id: int | None = None
    game_state_id: int | None = None
    try:
        canonical_event_id = _seed_canonical_event(suffix)
        game_state_id = _seed_game_state(suffix, canonical_event_id=canonical_event_id)

        # Pre-condition: the game_states row links the canonical event.
        with get_cursor() as cur:
            cur.execute(
                "SELECT canonical_event_id FROM game_states WHERE id = %s",
                (game_state_id,),
            )
            pre_row = cur.fetchone()
        assert pre_row is not None
        assert pre_row["canonical_event_id"] == canonical_event_id, (
            "game_states.canonical_event_id must reference the seeded canonical_event pre-DELETE"
        )

        # Trigger the SET NULL cascade.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_events WHERE id = %s",
                (canonical_event_id,),
            )
        # The canonical_events row no longer exists -- skip cleanup.
        canonical_event_id = None

        # Post-condition: game_states row survives with canonical_event_id NULL.
        with get_cursor() as cur:
            cur.execute(
                "SELECT canonical_event_id FROM game_states WHERE id = %s",
                (game_state_id,),
            )
            post_row = cur.fetchone()
        assert post_row is not None, (
            "game_states row must survive DELETE FROM canonical_events "
            "(SET NULL preserves the platform-tier row per ADR-118 V2.42 "
            "sub-amendment B canonical-outlives-platform polarity)"
        )
        assert post_row["canonical_event_id"] is None, (
            f"game_states.canonical_event_id must be NULL post-DELETE-FROM-canonical_events; "
            f"got {post_row['canonical_event_id']!r}"
        )
    finally:
        if game_state_id is not None:
            _cleanup_game_state(game_state_id)
        if canonical_event_id is not None:
            _cleanup_canonical_event(canonical_event_id)


def test_games_canonical_event_id_set_null_on_canonical_events_delete(db_pool: Any) -> None:
    """DELETE canonical_events row cascades games.canonical_event_id to NULL.

    Sibling of the game_states test -- exercises the second FK shipped
    in slot 0080.  Same shape: seed parent, seed child with FK, delete
    parent, assert child survives with FK NULLed.
    """
    suffix = uuid.uuid4().hex[:8]
    canonical_event_id: int | None = None
    game_id: int | None = None
    try:
        canonical_event_id = _seed_canonical_event(suffix)
        game_id = _seed_game(suffix, canonical_event_id=canonical_event_id)

        # Pre-condition.
        with get_cursor() as cur:
            cur.execute(
                "SELECT canonical_event_id FROM games WHERE id = %s",
                (game_id,),
            )
            pre_row = cur.fetchone()
        assert pre_row is not None
        assert pre_row["canonical_event_id"] == canonical_event_id, (
            "games.canonical_event_id must reference the seeded canonical_event pre-DELETE"
        )

        # Trigger the SET NULL cascade.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_events WHERE id = %s",
                (canonical_event_id,),
            )
        canonical_event_id = None

        # Post-condition.
        with get_cursor() as cur:
            cur.execute(
                "SELECT canonical_event_id FROM games WHERE id = %s",
                (game_id,),
            )
            post_row = cur.fetchone()
        assert post_row is not None, "games row must survive DELETE FROM canonical_events"
        assert post_row["canonical_event_id"] is None, (
            f"games.canonical_event_id must be NULL post-DELETE-FROM-canonical_events; "
            f"got {post_row['canonical_event_id']!r}"
        )
    finally:
        if game_id is not None:
            _cleanup_game(game_id)
        if canonical_event_id is not None:
            _cleanup_canonical_event(canonical_event_id)


# =============================================================================
# Group 6: FK violation propagation -- INSERT child with non-existent
# canonical_event_id raises ForeignKeyViolation.
# =============================================================================


def test_game_states_fk_violation_on_nonexistent_canonical_event(
    db_pool: Any,
) -> None:
    """INSERT game_states with non-existent canonical_event_id raises FK violation.

    The VALIDATE CONSTRAINT step proved no orphans existed at migration
    time; THIS test asserts FK enforcement on NEW writes.  The two
    properties are independent: NOT VALID briefly suspends scan-of-existing-
    rows enforcement, but always-on enforcement of NEW writes is part of
    the constraint definition itself.

    Uses an absurdly large id (2^31) that cannot collide with an actual
    canonical_events.id (BIGSERIAL starts at 1, dev DB has at most a few
    canonical_events rows).
    """
    nonexistent_id = (
        9_223_372_036_854_775_807  # BIGINT_MAX; impossible to collide with any real BIGSERIAL id
    )
    suffix = uuid.uuid4().hex[:8]
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO game_states (
                    espn_event_id, game_state_key, league, league_id,
                    game_status, data_source, canonical_event_id
                )
                VALUES (
                    %s, %s, 'nfl',
                    (SELECT id FROM leagues WHERE league_key = 'nfl'),
                    'pre', 'espn', %s
                )
                """,
                (
                    f"TEST-0080-FKV-{suffix}",
                    f"TEST-0080-FKV-GSK-{suffix}",
                    nonexistent_id,
                ),
            )


def test_games_fk_violation_on_nonexistent_canonical_event(db_pool: Any) -> None:
    """INSERT games with non-existent canonical_event_id raises FK violation."""
    nonexistent_id = (
        9_223_372_036_854_775_807  # BIGINT_MAX; impossible to collide with any real BIGSERIAL id
    )
    suffix = uuid.uuid4().hex[:8]
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO games (
                    sport, game_date, home_team_code, away_team_code, season,
                    league, neutral_site, is_playoff, game_status,
                    data_source, sport_id, league_id, game_key,
                    canonical_event_id
                )
                VALUES (
                    'football', CURRENT_DATE, %s, %s, 2026,
                    'nfl', FALSE, FALSE, 'scheduled',
                    'espn',
                    (SELECT id FROM sports WHERE sport_key = 'football'),
                    (SELECT id FROM leagues WHERE league_key = 'nfl'),
                    %s, %s
                )
                """,
                (
                    f"80FH{suffix[:6]}",
                    f"80FA{suffix[:6]}",
                    f"GAME-TEST-0080-FKV-{suffix}",
                    nonexistent_id,
                ),
            )


# =============================================================================
# Group 7: NULL acceptance -- INSERT with canonical_event_id=NULL succeeds
# on both tables (column nullable, FK doesn't fire on NULL).
# =============================================================================


def test_game_states_accepts_null_canonical_event_id(db_pool: Any) -> None:
    """INSERT game_states with canonical_event_id=NULL succeeds.

    The column is nullable (build spec § 2: backfill deferred); existing
    rows are NULL until the matcher binds them.  This test asserts the
    nullable-FK contract: NULL is a legal value, FK doesn't fire on
    NULL per SQL standard semantics.
    """
    suffix = uuid.uuid4().hex[:8]
    game_state_id: int | None = None
    try:
        game_state_id = _seed_game_state(suffix, canonical_event_id=None)
        with get_cursor() as cur:
            cur.execute(
                "SELECT canonical_event_id FROM game_states WHERE id = %s",
                (game_state_id,),
            )
            row = cur.fetchone()
        assert row is not None, "game_states row must exist post-INSERT"
        assert row["canonical_event_id"] is None, (
            "game_states.canonical_event_id must be NULL when explicitly set NULL; "
            f"got {row['canonical_event_id']!r}"
        )
    finally:
        if game_state_id is not None:
            _cleanup_game_state(game_state_id)


def test_games_accepts_null_canonical_event_id(db_pool: Any) -> None:
    """INSERT games with canonical_event_id=NULL succeeds."""
    suffix = uuid.uuid4().hex[:8]
    game_id: int | None = None
    try:
        game_id = _seed_game(suffix, canonical_event_id=None)
        with get_cursor() as cur:
            cur.execute(
                "SELECT canonical_event_id FROM games WHERE id = %s",
                (game_id,),
            )
            row = cur.fetchone()
        assert row is not None
        assert row["canonical_event_id"] is None, (
            "games.canonical_event_id must be NULL when explicitly set NULL; "
            f"got {row['canonical_event_id']!r}"
        )
    finally:
        if game_id is not None:
            _cleanup_game(game_id)


# =============================================================================
# Group 8: Population-safety surface -- the migration only ADDs schema;
# pre-existing rows are unaffected.
#
# This is exercised partially here (default values on existing rows are
# NULL after ADD COLUMN) and fully by the round-trip CI gate (PR #1081).
# We test the SHAPE-LEVEL invariant: every existing row's
# canonical_event_id is NULL post-migration.  A schema bug that
# accidentally backfilled a non-NULL default would surface here.
# =============================================================================


# (table_name, natural_key_column, test_row_prefix) — each table's
# natural-key column is distinct (espn_event_id on game_states, game_key
# on games), so the test-row exclusion uses a per-table column reference.
# Passing these via parametrize keeps the test body table-agnostic without
# requiring CASE/conditional SQL across columns that don't co-exist on
# both tables (PG plans the WHERE expression for ALL columns, even those
# under a literal-false branch — the cross-table OR form fails at parse
# time).
_POPULATION_SAFETY_FIXTURES: tuple[tuple[str, str, str], ...] = (
    ("game_states", "espn_event_id", "TEST-0080-%"),
    ("games", "game_key", "GAME-TEST-0080-%"),
)


@pytest.mark.parametrize(
    ("table_name", "natural_key_column", "test_row_prefix"),
    _POPULATION_SAFETY_FIXTURES,
)
def test_existing_rows_have_null_canonical_event_id(
    db_pool: Any,
    table_name: str,
    natural_key_column: str,
    test_row_prefix: str,
) -> None:
    """Every pre-existing row has canonical_event_id=NULL post-migration.

    Slot 0080 ships ADD COLUMN with no DEFAULT clause.  PG semantics:
    no DEFAULT + nullable column => existing rows get NULL.  This test
    asserts the shape-level invariant by counting non-NULL values that
    were NOT inserted by THIS test run.

    NOTE: tests in this file use unique espn_event_id / game_key
    prefixes (``TEST-0080-*``); a row with a non-NULL canonical_event_id
    that does NOT match those prefixes would indicate either (a) a
    sibling test that bound a row to a canonical event and didn't clean
    up, or (b) a real backfill that snuck in.  Both are fixable; the
    assertion's value is in surfacing them at all.

    The COUNT(*) WHERE canonical_event_id IS NOT NULL form catches the
    pathological "DEFAULT 0" or "DEFAULT some-real-id" migration bug
    that would otherwise pass column-shape inspection.
    """
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT count(*) AS non_null_count
            FROM {table_name}
            WHERE canonical_event_id IS NOT NULL
              AND {natural_key_column} NOT LIKE %s
            """,  # noqa: S608 -- table_name + natural_key_column are
            # hardcoded literals from _POPULATION_SAFETY_FIXTURES; PG
            # identifier-binding limitation requires f-string for FROM
            # clause and column reference.  Project precedent:
            # feedback_ruff_s608_on_partition_ddl_fstrings.md (slots
            # 0072 / 0074 / 0078 same suppression).
            (test_row_prefix,),
        )
        row = cur.fetchone()
    assert row is not None
    assert row["non_null_count"] == 0, (
        f"{table_name} must have 0 non-NULL canonical_event_id values from "
        f"pre-existing rows post-Migration-0080 (slot 0080 ADD COLUMN with no "
        f"DEFAULT => existing rows get NULL); got {row['non_null_count']!r}"
    )
