"""#933 regression — ESPN poller CRUD-path smoke for team-code drift.

The existing ``test_espn_game_poller_integration.py`` suite is built on
``MagicMock``-patched CRUD callables (``@patch(...upsert_game_state)``,
``@patch(...create_venue)``, etc.), which short-circuits the real
``get_or_create_game`` code path this regression is designed to exercise.
Restructuring that suite to run against the real DB is out of scope for
the #933 fix.

Instead, this file reproduces the operational scenario that caused the
poller crashes (#933) directly at the ``get_or_create_game`` layer — the
identical call-path the poller invokes from ``_sync_game_to_db`` (see
``src/precog/schedulers/espn_game_poller.py:1378``).  It seeds three rows
with the known-drifted ``espn_event_id`` values from production
(``401856661``, ``401856663``, ``401858427`` — left as TEST sentinels to
avoid collision with any production-synced test-DB rows) and verifies
the upsert cycle completes without raising.

Pre-0066: any of these three would have raised ``psycopg2.errors.UniqueViolation``
on the second call with a drifted team code.  Post-0066: all three must
upsert cleanly.

Issue: #933
Epic: #935
Related: deeper poller integration coverage tracked separately (file
    ``tests/integration/schedulers/test_espn_game_poller_integration.py``
    would need MagicMock -> real-DB refactor to cover this end-to-end).

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


# Known-drifted production rows (id / espn_event_id pairs from design memo).
# Wrapped in TEST- prefix so parallel CI runs cannot collide with real
# production-synced data in the test DB.  Each tuple:
#   (sentinel_prefix, original_home_code, drifted_home_code, away_code, league)
_DRIFT_FIXTURES: list[tuple[str, str, str, str, str]] = [
    ("TEST-933-EVT1", "MISS", "MS", "LOU", "ncaaf"),
    ("TEST-933-EVT2", "ALA", "AL", "TENN", "ncaaf"),
    ("TEST-933-EVT3", "TEX", "TX", "OKLA", "ncaaf"),
]


def _sentinel(prefix: str) -> str:
    """Return a run-unique sentinel to avoid parallel-CI collisions."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _cleanup(espn_event_ids: list[str]) -> None:
    """Remove games rows with any of the given test sentinels."""
    if not espn_event_ids:
        return
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM games WHERE espn_event_id = ANY(%s)",
            (espn_event_ids,),
        )


def test_known_drifted_events_upsert_cleanly(db_pool: Any) -> None:
    """All three drifted-team-code scenarios from #933 upsert without UniqueViolation.

    Models the poller flow:
        Cycle 1: upstream ESPN returns (sport, date, ORIGINAL, away) with espn_event_id=X
        Cycle 2: upstream ESPN returns (sport, date, DRIFTED, away) with espn_event_id=X

    Pre-0066: cycle 2 raised UniqueViolation on idx_games_espn_event.
    Post-0066: both cycles succeed; two rows coexist sharing espn_event_id=X.
    """
    sentinels = [_sentinel(prefix) for (prefix, *_) in _DRIFT_FIXTURES]
    _cleanup(sentinels)

    try:
        for espn_event, (_prefix, original_code, drifted_code, away_code, league) in zip(
            sentinels, _DRIFT_FIXTURES, strict=True
        ):
            # Cycle 1: seed with original team code.
            id_cycle_1 = get_or_create_game(
                sport="football",
                game_date=date(2026, 9, 5),
                home_team_code=original_code,
                away_team_code=away_code,
                league=league,
                espn_event_id=espn_event,
            )
            assert id_cycle_1 is not None, f"Cycle 1 upsert failed for espn_event={espn_event!r}"

            # Cycle 2: drifted team code, SAME espn_event_id — pre-0066 this
            # raised UniqueViolation; post-0066 it must succeed.
            id_cycle_2 = get_or_create_game(
                sport="football",
                game_date=date(2026, 9, 5),
                home_team_code=drifted_code,
                away_team_code=away_code,
                league=league,
                espn_event_id=espn_event,
            )
            assert id_cycle_2 is not None, (
                f"Cycle 2 upsert (drifted code {drifted_code!r}) failed for "
                f"espn_event={espn_event!r} — did the UNIQUE come back?"
            )
            assert id_cycle_2 != id_cycle_1, (
                f"Drifted code must produce a new row (business key misses "
                f"ON CONFLICT target); got id_cycle_2={id_cycle_2!r} == "
                f"id_cycle_1={id_cycle_1!r}"
            )

        # Post-condition: all three sentinels have exactly 2 rows each,
        # and the per-sentinel rows share the external key.
        with get_cursor() as cur:
            cur.execute(
                "SELECT espn_event_id, COUNT(*) AS c "
                "FROM games WHERE espn_event_id = ANY(%s) "
                "GROUP BY espn_event_id ORDER BY espn_event_id",
                (sentinels,),
            )
            rows = cur.fetchall()
        assert len(rows) == 3, f"Expected 3 sentinel event-ids; got {len(rows)}"
        for r in rows:
            assert int(r["c"]) == 2, (
                f"Expected 2 rows per sentinel espn_event_id={r['espn_event_id']!r}; got {r['c']}"
            )
    finally:
        _cleanup(sentinels)
