"""Integration tests for migration 0066 -- demote games.espn_event_id UNIQUE.

Verifies the POST-MIGRATION state of ``idx_games_espn_event`` on the
``games`` table, plus the end-to-end behaviour of ``get_or_create_game``
under the ESPN team-code-drift scenario that motivated #933.

Under the three-tier identity model (Epic #935), ``espn_event_id`` is an
EXTERNAL identifier and MUST NOT be UNIQUE on ``games``.  Pre-0066, a
partial UNIQUE (from migration 0035) would raise ``UniqueViolation`` when
the ESPN poller observed upstream team-code drift (e.g., ``MISS -> MS``)
between polling cycles, because the business-key ON CONFLICT would miss
and the subsequent INSERT would then trip the external-key UNIQUE.

Test groups:
    - TestIndexShape: ``idx_games_espn_event`` exists, is NON-UNIQUE,
      retains its partial WHERE predicate, and ``uq_games_matchup`` /
      ``games_pkey`` / ``idx_games_game_key`` remain UNIQUE.
    - TestDriftRegression: seeding a row under one team-code variant and
      then calling ``get_or_create_game`` with a drifted team code +
      identical ``espn_event_id`` succeeds and produces two rows sharing
      the external key (the exact operational scenario from #933).
    - TestOnConflictBranch: seeding + re-upserting the SAME business key
      with the SAME ``espn_event_id`` preserves a single row and
      advances ``updated_at`` (smoke test — business-key path still works).

Migration round-trip (upgrade -> downgrade -> re-upgrade) is verified
by the PM during build via manual alembic invocation against the test
DB. An automated round-trip test would conflict with pytest-xdist
parallel workers (one worker downgrading mid-run would break other
workers' DDL assertions). Same pattern documented in
``test_migration_0052_0055_execution_environment.py``.

Issue: #933
Epic: #935 (Identity Semantics Audit & Hardening — three-tier identity)

Markers:
    @pytest.mark.integration: real DB required.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import pytest

from precog.database.connection import get_cursor
from precog.database.crud_game_states import get_or_create_game

pytestmark = [pytest.mark.integration]


# =============================================================================
# Test sentinels (unique per parallel CI run via UUID suffix)
# =============================================================================


def _sentinel(prefix: str) -> str:
    """Return a unique test sentinel so parallel CI runs don't collide."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _cleanup_test_rows(espn_event_ids: list[str]) -> None:
    """Remove any games rows with matching TEST-933-* espn_event_id sentinels."""
    if not espn_event_ids:
        return
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM games WHERE espn_event_id = ANY(%s)",
            (espn_event_ids,),
        )


# =============================================================================
# Group 1: Index shape post-0066
# =============================================================================


def test_idx_games_espn_event_is_non_unique(db_pool: Any) -> None:
    """``idx_games_espn_event`` exists and is NOT UNIQUE post-0066."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexdef FROM pg_indexes
            WHERE tablename = 'games' AND indexname = 'idx_games_espn_event'
            """
        )
        row = cur.fetchone()
    assert row is not None, "idx_games_espn_event must exist post-0066"
    indexdef = row["indexdef"]
    # Post-0066 invariant: the index is partial-btree, NOT unique.
    assert "CREATE UNIQUE" not in indexdef, (
        f"idx_games_espn_event must be NON-UNIQUE post-0066 (#933 / Epic #935); got: {indexdef}"
    )
    assert "CREATE INDEX" in indexdef, (
        f"idx_games_espn_event must be a btree index; got: {indexdef}"
    )
    # Partial predicate preserved (historical imports write NULL).
    assert "espn_event_id IS NOT NULL" in indexdef, (
        f"idx_games_espn_event must retain partial WHERE predicate; got: {indexdef}"
    )


def test_only_one_index_on_espn_event_id_column(db_pool: Any) -> None:
    """Pin index-name reuse: exactly one index on ``games(espn_event_id)``.

    Guards against a future migration silently creating a parallel
    ``idx_games_espn_event_v2`` (e.g., re-adding UNIQUE under a new name
    and leaving the non-unique sibling in place). Such a state would
    defeat the Epic #935 principle while passing the other post-0066
    invariants. This test fails loud if that drift happens.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS n FROM pg_indexes
            WHERE tablename = 'games'
              AND indexdef LIKE '%(espn_event_id)%'
            """
        )
        row = cur.fetchone()
    assert row is not None
    assert row["n"] == 1, (
        f"expected exactly one index on games(espn_event_id); found {row['n']}. "
        f"If a second index was added, verify it does not re-introduce UNIQUE on "
        f"the external identifier (Epic #935 forbids)."
    )


def test_uq_games_matchup_remains_unique(db_pool: Any) -> None:
    """The business-key UNIQUE remains in place — internal identity is preserved."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexdef FROM pg_indexes
            WHERE tablename = 'games' AND indexname = 'uq_games_matchup'
            """
        )
        row = cur.fetchone()
    assert row is not None, "uq_games_matchup must exist"
    assert "CREATE UNIQUE" in row["indexdef"], (
        f"uq_games_matchup must remain UNIQUE post-0066; got: {row['indexdef']}"
    )


def test_idx_games_game_key_remains_unique(db_pool: Any) -> None:
    """The internal reference-key UNIQUE (from 0062) remains in place."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexdef FROM pg_indexes
            WHERE tablename = 'games' AND indexname = 'idx_games_game_key'
            """
        )
        row = cur.fetchone()
    assert row is not None, "idx_games_game_key must exist (from migration 0062)"
    assert "CREATE UNIQUE" in row["indexdef"], (
        f"idx_games_game_key must remain UNIQUE post-0066; got: {row['indexdef']}"
    )


# =============================================================================
# Group 2: Drift regression — #933's exact scenario
# =============================================================================


def test_team_code_drift_with_same_espn_event_id_succeeds(db_pool: Any) -> None:
    """Two rows may share ``espn_event_id`` when business keys drift.

    Regression for #933: the ESPN poller observes upstream team-code
    drift mid-season (e.g., ``MISS`` -> ``MS``).  The drifted code
    misses the ``uq_games_matchup`` ON CONFLICT target, and the INSERT
    proceeds with the same ``espn_event_id``.  Post-0066, this is
    allowed — no UniqueViolation — and two rows coexist sharing
    ``espn_event_id``.  Pre-0066, this raised.
    """
    espn_event = _sentinel("TEST-933-A")
    _cleanup_test_rows([espn_event])

    try:
        # Row A: seed with the original team code.
        id_a = get_or_create_game(
            sport="football",
            game_date=date(2026, 9, 5),
            home_team_code="MISS",
            away_team_code="LOU",
            league="ncaaf",
            espn_event_id=espn_event,
        )
        assert id_a is not None

        # Row B: drifted team code, SAME espn_event_id.  Post-0066 this
        # must succeed (pre-0066 it would raise psycopg2.errors.UniqueViolation
        # on the partial UNIQUE).
        id_b = get_or_create_game(
            sport="football",
            game_date=date(2026, 9, 5),
            home_team_code="MS",
            away_team_code="LOU",
            league="ncaaf",
            espn_event_id=espn_event,
        )
        assert id_b is not None
        assert id_b != id_a, (
            "Drifted team code must produce a DIFFERENT row (business key misses "
            "ON CONFLICT target)"
        )

        # Post-condition: both rows share the external key.
        with get_cursor() as cur:
            cur.execute(
                "SELECT id, home_team_code, espn_event_id FROM games "
                "WHERE espn_event_id = %s ORDER BY id",
                (espn_event,),
            )
            rows = cur.fetchall()
        assert len(rows) == 2, (
            f"Expected 2 rows sharing espn_event_id={espn_event!r}; got {len(rows)}"
        )
        codes = {r["home_team_code"] for r in rows}
        assert codes == {"MISS", "MS"}, f"Expected both drift variants to coexist; got {codes!r}"
        assert all(r["espn_event_id"] == espn_event for r in rows), (
            "Both rows must share the external key"
        )
    finally:
        _cleanup_test_rows([espn_event])


# =============================================================================
# Group 3: ON CONFLICT branch smoke (business-key path still works)
# =============================================================================


def test_same_business_key_upsert_preserves_single_row(db_pool: Any) -> None:
    """Re-upserting the SAME business key with SAME espn_event_id preserves 1 row.

    Business-key ON CONFLICT is the real identity guarantee on ``games``.
    This smoke test confirms 0066 did not accidentally break it —
    upserting a second time with an identical business key keeps the
    single row and advances ``updated_at``.
    """
    espn_event = _sentinel("TEST-933-B")
    _cleanup_test_rows([espn_event])

    try:
        # Initial insert.
        id_first = get_or_create_game(
            sport="football",
            game_date=date(2026, 9, 12),
            home_team_code="KC",
            away_team_code="BAL",
            league="nfl",
            espn_event_id=espn_event,
        )
        assert id_first is not None

        with get_cursor() as cur:
            cur.execute(
                "SELECT id, updated_at FROM games WHERE espn_event_id = %s",
                (espn_event,),
            )
            pre_rows = cur.fetchall()
        assert len(pre_rows) == 1, "Expected exactly 1 row after first insert"
        pre_updated_at = pre_rows[0]["updated_at"]

        # Re-upsert with the SAME business key — ON CONFLICT path.
        id_second = get_or_create_game(
            sport="football",
            game_date=date(2026, 9, 12),
            home_team_code="KC",
            away_team_code="BAL",
            league="nfl",
            espn_event_id=espn_event,
            game_status="final",  # force updated_at to advance
            home_score=24,
            away_score=21,
        )
        assert id_second == id_first, (
            "ON CONFLICT path must return the existing row id, not allocate a new one"
        )

        with get_cursor() as cur:
            cur.execute(
                "SELECT id, updated_at, game_status, home_score "
                "FROM games WHERE espn_event_id = %s",
                (espn_event,),
            )
            post_rows = cur.fetchall()
        assert len(post_rows) == 1, (
            f"Same business key must preserve single row; got {len(post_rows)} rows"
        )
        assert post_rows[0]["updated_at"] >= pre_updated_at, (
            "updated_at must advance (or stay equal if same clock tick) on re-upsert"
        )
        assert post_rows[0]["game_status"] == "final"
        assert post_rows[0]["home_score"] == 24
    finally:
        _cleanup_test_rows([espn_event])


# =============================================================================
# Group 4: Migration round-trip is verified manually by the PM during build.
# See the module docstring for the same rationale applied in
# test_migration_0052_0055_execution_environment.py -- an automated up/down
# test would conflict with pytest-xdist parallel workers.
# =============================================================================
