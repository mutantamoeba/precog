"""Integration tests for Migration 0077 -- canonical_events FK ON DELETE SET NULL.

Verifies the POST-MIGRATION state of the two ``canonical_events`` FK
constraints retrofitted by Migration 0077 (ADR-118 V2.42 sub-amendment B,
issue #1075).  Migration 0077 ships:

    1. ``ALTER TABLE canonical_events DROP CONSTRAINT
       canonical_events_game_id_fkey`` followed by ADD CONSTRAINT with
       ``ON DELETE SET NULL`` and the original constraint name preserved.
    2. Same DROP/ADD pair for ``canonical_events_series_id_fkey``.

Test groups:
    - TestConstraintPolarity: both FKs render with ``ON DELETE SET NULL``
      via ``pg_get_constraintdef``; constraint NAMES are preserved across
      the DROP/ADD pair (Holden-FK -- PG default-generated names would
      break the pinned-by-name assertion in test_migration_0067 lines
      400-450).
    - TestBehavioralCascadeGameId: INSERT a games row, INSERT a
      canonical_events row referencing it via game_id, DELETE the games
      row, ASSERT the canonical_events row survives with
      ``game_id IS NULL``.
    - TestBehavioralCascadeSeriesId: sibling test for series.

Cross-references the round-trip CI gate (PR #1081 / Issue #1066): the
``downgrade()`` reverses the ALTER pair cleanly (DROP CONSTRAINT + ADD
CONSTRAINT WITHOUT ON DELETE clause -- restores PG default NO ACTION
matching the Migration 0067 pre-retrofit state).  Round-trip is exercised
by ``tests/integration/migrations/test_round_trip.py`` which programmatically
runs ``downgrade(0076) -> upgrade head`` on every parametrized revision
post-0067.

Issue: #1075 (ADR-118 V2.42 sub-amendment B retrofit)
ADR: ADR-118 V2.42 sub-amendment B (canonical_events FK ON DELETE SET NULL)
Council: ``memory/design_review_0076_synthesis.md`` (Holden + Galadriel +
    Miles + Uhura, session 83)

Markers:
    @pytest.mark.integration: real DB required.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from precog.database.connection import get_cursor

pytestmark = [pytest.mark.integration]


# Constraint names retrofitted in slot 0077.  Pattern 73 SSOT for the
# pinned-name list; the migration's ``_FK_CONSTRAINTS`` tuple + the
# test_migration_0067 parametrize values + this list must all agree, or
# Holden-FK constraint-name preservation has drifted.
_RETROFITTED_CONSTRAINTS: tuple[tuple[str, str, str], ...] = (
    # (constraint_name, fk_column, parent_table)
    ("canonical_events_game_id_fkey", "game_id", "games"),
    ("canonical_events_series_id_fkey", "series_id", "series"),
)


# =============================================================================
# Seed helpers — minimal-FK-chain platform-tier rows so the cascade tests
# can DELETE the parent and observe the SET NULL behavior.
# =============================================================================


def _seed_game(suffix: str) -> int:
    """Seed a games row with minimal FK chain (sport/league seeded by 0060).

    Uses NULL home_team_id / away_team_id / venue_id (all NULLABLE per the
    games schema) so the test does not need to seed teams + venues.  Pairs
    with ``_cleanup_game(returned_id)`` in a finally block.
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO games (
                sport, game_date, home_team_code, away_team_code, season,
                league, neutral_site, is_playoff, game_status,
                data_source, sport_id, league_id, game_key
            )
            VALUES (
                'football', CURRENT_DATE, %s, %s, 2026,
                'nfl', FALSE, FALSE, 'scheduled',
                'espn',
                (SELECT id FROM sports WHERE sport_key = 'football'),
                (SELECT id FROM leagues WHERE league_key = 'nfl'),
                %s
            )
            RETURNING id
            """,
            # Team codes truncate to 10 chars; keep `77` slot marker + H/A
            # differentiator FIRST so the suffix entropy survives. The naive
            # `f"TEST-0077-HOME-{suffix}"[:10]` form yields `"TEST-0077-"`
            # for both home and away (suffix dropped), which would collide
            # under pytest-xdist multi-worker runs of this test on the same
            # game_date (CURRENT_DATE) — uq_games_matchup violates.
            (
                f"77H{suffix[:7]}",
                f"77A{suffix[:7]}",
                f"GAME-TEST-0077-{suffix}",
            ),
        )
        return int(cur.fetchone()["id"])


def _cleanup_game(game_id: int) -> None:
    """Best-effort delete of a games row seeded by ``_seed_game``.

    Swallows exceptions so a cleanup failure (e.g., orphaned child row from
    a prior crashed test) doesn't mask the original test failure when called
    from a finally block.
    """
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM games WHERE id = %s", (game_id,))
    except Exception:
        pass


def _seed_series(suffix: str) -> int:
    """Seed a series row backed by the existing 'kalshi' platform.

    Pairs with ``_cleanup_series(returned_id)`` in a finally block.
    """
    series_key = f"TEST-0077-SER-{suffix}"
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO series (
                series_key, platform_id, external_id, category, title
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                series_key,
                "kalshi",
                f"TEST-0077-SER-EXT-{suffix}",
                "sports",
                f"Migration 0077 test series ({suffix})",
            ),
        )
        return int(cur.fetchone()["id"])


def _cleanup_series(series_id: int) -> None:
    """Best-effort delete of a series row seeded by ``_seed_series``.

    Swallows exceptions so a cleanup failure (e.g., orphaned child row from
    a prior crashed test) doesn't mask the original test failure when called
    from a finally block.
    """
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM series WHERE id = %s", (series_id,))
    except Exception:
        pass


def _seed_canonical_event(
    suffix: str,
    *,
    game_id: int | None = None,
    series_id: int | None = None,
) -> int:
    """Seed a canonical_events row with optional game_id / series_id FKs.

    Mirrors the shape of ``_canonical_event_helpers._seed_canonical_event``
    but accepts game_id / series_id parameters so the cascade tests can
    bind the row to a specific platform-tier parent.

    Caller MUST pair with ``_cleanup_canonical_event(returned_id)`` in a
    finally block.
    """
    nk_hash = f"TEST-0077-evt-{suffix}".encode()
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
                game_id,
                series_id,
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
                %s,
                %s,
                'proposed'
            )
            RETURNING id
            """,
            (nk_hash, f"Test event ({suffix})", game_id, series_id),
        )
        return int(cur.fetchone()["id"])


def _cleanup_canonical_event(canonical_event_id: int) -> None:
    """Best-effort delete of a canonical_events row."""
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM canonical_events WHERE id = %s",
            (canonical_event_id,),
        )


# =============================================================================
# Group 1: Constraint polarity (positive assertion mirrors test_0067 line 442)
# =============================================================================


@pytest.mark.parametrize(
    ("constraint_name", "fk_column", "parent_table"),
    _RETROFITTED_CONSTRAINTS,
)
def test_constraint_renders_with_set_null_action(
    db_pool: Any,
    constraint_name: str,
    fk_column: str,
    parent_table: str,
) -> None:
    """``pg_get_constraintdef`` emits ``ON DELETE SET NULL`` for both retrofitted FKs.

    Positive assertion (Galadriel's restructure recommendation): asserts
    the SET NULL clause is PRESENT in the constraint definition rather
    than asserting absence-of-other-clauses.  Mirrors the assertion in
    test_migration_0067 lines 400-450 -- this test exists as a slot-
    specific witness in addition to the 0067 test, so a regression that
    reverts the polarity surfaces under both filenames (the 0067 file
    is the canonical home; this file is a slot-0077 witness for
    discoverability when grepping by migration number).
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_events'::regclass
              AND conname = %s
            """,
            (constraint_name,),
        )
        row = cur.fetchone()
    assert row is not None, f"{constraint_name} must exist on canonical_events post-Migration-0077"
    fk_def = row["def"]
    assert "ON DELETE SET NULL" in fk_def, (
        f"{constraint_name} must include 'ON DELETE SET NULL' post-Migration-0077; got: {fk_def}"
    )
    # Belt-and-suspenders: confirm the FK still references the expected
    # parent table + column.  Names alone are not enough -- a future
    # migration that re-pointed the FK to a different table while
    # keeping the constraint name would otherwise pass.
    assert f"REFERENCES {parent_table}(id)" in fk_def, (
        f"{constraint_name} must REFERENCE {parent_table}(id); got: {fk_def}"
    )
    assert f"FOREIGN KEY ({fk_column})" in fk_def, (
        f"{constraint_name} must be FOREIGN KEY ({fk_column}); got: {fk_def}"
    )


# =============================================================================
# Group 2: Behavioral cascade — DELETE games, expect canonical_events.game_id
# becomes NULL with the row preserved.
# =============================================================================


def test_canonical_events_game_id_set_null_on_games_delete(db_pool: Any) -> None:
    """DELETE FROM games cascades canonical_events.game_id to NULL; row survives.

    End-to-end behavioral evidence that Migration 0077's SET NULL
    polarity actually fires under the canonical-outlives-platform contract
    of ADR-118 V2.42 sub-amendment B.

    Sequence:
        1. Seed a games row.
        2. Seed a canonical_events row with game_id pointing at the game.
        3. DELETE the games row.
        4. Assert the canonical_events row still exists.
        5. Assert the canonical_events row has game_id = NULL.
    """
    suffix = uuid.uuid4().hex[:8]
    game_id: int | None = None
    canonical_event_id: int | None = None
    try:
        game_id = _seed_game(suffix)
        canonical_event_id = _seed_canonical_event(suffix, game_id=game_id)

        # Pre-condition sanity check: the canonical_events row links the game.
        with get_cursor() as cur:
            cur.execute(
                "SELECT game_id FROM canonical_events WHERE id = %s",
                (canonical_event_id,),
            )
            pre_row = cur.fetchone()
        assert pre_row is not None
        assert pre_row["game_id"] == game_id, (
            "canonical_events.game_id must reference the seeded game pre-DELETE"
        )

        # Trigger the SET NULL cascade by deleting the games row.
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM games WHERE id = %s", (game_id,))
        # Cleanup pointer adjustment: the games row no longer exists, so
        # the finally-block cleanup must skip the games-DELETE.  We mark
        # the local variable to None so the finally block does the right
        # thing.
        game_id = None

        # Post-condition: canonical_events row survives with game_id NULL.
        with get_cursor() as cur:
            cur.execute(
                "SELECT game_id, series_id FROM canonical_events WHERE id = %s",
                (canonical_event_id,),
            )
            post_row = cur.fetchone()
        assert post_row is not None, (
            "canonical_events row must survive DELETE FROM games "
            "(SET NULL preserves the canonical row per ADR-118 V2.42 "
            "sub-amendment B)"
        )
        assert post_row["game_id"] is None, (
            f"canonical_events.game_id must be NULL post-DELETE-FROM-games; "
            f"got {post_row['game_id']!r}"
        )
    finally:
        if canonical_event_id is not None:
            _cleanup_canonical_event(canonical_event_id)
        if game_id is not None:
            _cleanup_game(game_id)


def test_canonical_events_series_id_set_null_on_series_delete(db_pool: Any) -> None:
    """DELETE FROM series cascades canonical_events.series_id to NULL; row survives.

    Sibling of the game_id test -- exercises the second FK retrofitted in
    slot 0077.  Same shape: seed parent, seed child with FK, delete
    parent, assert child survives with FK NULLed.
    """
    suffix = uuid.uuid4().hex[:8]
    series_id: int | None = None
    canonical_event_id: int | None = None
    try:
        series_id = _seed_series(suffix)
        canonical_event_id = _seed_canonical_event(suffix, series_id=series_id)

        # Pre-condition.
        with get_cursor() as cur:
            cur.execute(
                "SELECT series_id FROM canonical_events WHERE id = %s",
                (canonical_event_id,),
            )
            pre_row = cur.fetchone()
        assert pre_row is not None
        assert pre_row["series_id"] == series_id, (
            "canonical_events.series_id must reference the seeded series pre-DELETE"
        )

        # Trigger the SET NULL cascade.
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM series WHERE id = %s", (series_id,))
        series_id = None

        # Post-condition.
        with get_cursor() as cur:
            cur.execute(
                "SELECT game_id, series_id FROM canonical_events WHERE id = %s",
                (canonical_event_id,),
            )
            post_row = cur.fetchone()
        assert post_row is not None, "canonical_events row must survive DELETE FROM series"
        assert post_row["series_id"] is None, (
            f"canonical_events.series_id must be NULL post-DELETE-FROM-series; "
            f"got {post_row['series_id']!r}"
        )
    finally:
        if canonical_event_id is not None:
            _cleanup_canonical_event(canonical_event_id)
        if series_id is not None:
            _cleanup_series(series_id)


def test_canonical_events_survives_when_both_fks_set_null(db_pool: Any) -> None:
    """Both FKs SET NULL independently; row survives with both columns NULL.

    Edge case: a canonical_events row referencing BOTH game_id AND
    series_id (rare but legal -- a sports-domain canonical event linking
    a recurring matchup that exists both as a single game AND as part of
    a multi-game series).  When BOTH parents are deleted, both FKs SET
    NULL independently; the row survives.
    """
    suffix = uuid.uuid4().hex[:8]
    game_id: int | None = None
    series_id: int | None = None
    canonical_event_id: int | None = None
    try:
        game_id = _seed_game(suffix)
        series_id = _seed_series(suffix)
        canonical_event_id = _seed_canonical_event(suffix, game_id=game_id, series_id=series_id)

        # Pre-condition: both FKs bound to their parents before the DELETE.
        # Mirrors the single-FK cascade tests' pre-state assertion so a
        # silent seed-helper failure to bind one of the two FKs would
        # surface here, not as a misleading post-state pass.
        with get_cursor() as cur:
            cur.execute(
                "SELECT game_id, series_id FROM canonical_events WHERE id = %s",
                (canonical_event_id,),
            )
            pre_row = cur.fetchone()
        assert pre_row is not None
        assert pre_row["game_id"] == game_id
        assert pre_row["series_id"] == series_id

        # Delete both parents.
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM games WHERE id = %s", (game_id,))
            cur.execute("DELETE FROM series WHERE id = %s", (series_id,))
        game_id = None
        series_id = None

        # Both FKs should be NULL on the surviving canonical_events row.
        with get_cursor() as cur:
            cur.execute(
                "SELECT game_id, series_id FROM canonical_events WHERE id = %s",
                (canonical_event_id,),
            )
            post_row = cur.fetchone()
        assert post_row is not None
        assert post_row["game_id"] is None
        assert post_row["series_id"] is None
    finally:
        if canonical_event_id is not None:
            _cleanup_canonical_event(canonical_event_id)
        if game_id is not None:
            _cleanup_game(game_id)
        if series_id is not None:
            _cleanup_series(series_id)
