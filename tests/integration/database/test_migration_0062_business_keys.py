"""Integration tests for migration 0062 — C2c business key columns.

Verifies the POST-MIGRATION state of ``market_key``, ``event_key``,
``game_state_key``, and ``game_key`` on their four tables, plus the
CRUD contracts that keep those columns populated through create and
SCD2 supersede paths.

Test groups:
    - TestBusinessKeyColumnsPresent: column exists, NOT NULL, VARCHAR,
      on each of markets/events/game_states/games.
    - TestBusinessKeyIndexes: full UNIQUE on non-SCD2 tables; partial
      UNIQUE WHERE row_current_ind=true on game_states.
    - TestBackfillFormat: every pre-migration row has a key matching
      the ``<PREFIX>-<id>`` pattern (sampled; full-scan for small tables).
    - TestCreateAssignsCanonicalKey: ``create_market`` / ``create_event``
      / ``create_game_state`` all produce ``<PREFIX>-<id>``.
    - TestUpsertGameStateCarriesKeyForward: **the critical SCD2
      contract** — on supersede, the NEW row carries the same
      ``game_state_key`` as the CLOSED row.  If this regresses, the
      logical-entity identity across SCD versions breaks.
    - TestGetOrCreateGamePaths: CREATE branch produces ``GAM-{id}``;
      CONFLICT branch preserves the existing ``game_key``.
    - TestHistoricalGamesBatchLoader: batch-inserted games all get
      non-TEMP ``GAM-<id>`` keys; ON CONFLICT rows keep existing keys.
    - TestUniquenessEnforced: markets/events/games reject duplicate
      keys; game_states rejects duplicate keys ONLY for current rows.

Issues: #791
Epic: #745 (Schema Hardening Arc, Cohort C2c)

Markers:
    @pytest.mark.integration: real DB required (testcontainer per ADR-057)
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import psycopg2
import pytest

from precog.database.connection import get_cursor
from precog.database.crud_events import create_event
from precog.database.crud_game_states import (
    create_game_state,
    get_or_create_game,
    upsert_game_state,
)
from precog.database.crud_markets import create_market

pytestmark = [pytest.mark.integration]


# =============================================================================
# Per-table spec (mirrors migration 0062 ``_KEY_SPEC``)
# =============================================================================

# (table, key_column, prefix, is_scd2)
_KEY_SPEC: list[tuple[str, str, str, bool]] = [
    ("markets", "market_key", "MKT", False),
    ("events", "event_key", "EVT", False),
    ("game_states", "game_state_key", "GST", True),
    ("games", "game_key", "GAM", False),
]


# =============================================================================
# Group 1: Column presence + type + nullability
# =============================================================================


@pytest.mark.parametrize(("table", "key_col", "prefix", "is_scd2"), _KEY_SPEC)
def test_business_key_column_exists_and_not_null(
    db_pool: Any, table: str, key_col: str, prefix: str, is_scd2: bool
) -> None:
    """Column exists, is VARCHAR, and is NOT NULL on every table."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
            """,
            (table, key_col),
        )
        row = cur.fetchone()
    assert row is not None, f"{table}.{key_col} column missing post-0062"
    assert row["data_type"] in ("character varying", "text"), (
        f"{table}.{key_col} has unexpected type: {row['data_type']}"
    )
    assert row["is_nullable"] == "NO", f"{table}.{key_col} must be NOT NULL"


# =============================================================================
# Group 2: Indexes
# =============================================================================


def test_non_scd2_tables_have_full_unique_index(db_pool: Any) -> None:
    """markets/events/games have a plain (non-partial) UNIQUE on <x>_key."""
    for table, key_col, _prefix, is_scd2 in _KEY_SPEC:
        if is_scd2:
            continue
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = %s AND indexname = %s
                """,
                (table, f"idx_{table}_{key_col}"),
            )
            row = cur.fetchone()
        assert row is not None, f"Missing UNIQUE index on {table}.{key_col}"
        indexdef = row["indexdef"]
        assert "UNIQUE" in indexdef, f"{table}.{key_col} index must be UNIQUE"
        # Full (non-partial) UNIQUE: no WHERE clause in the index def.
        assert " WHERE " not in indexdef, (
            f"{table}.{key_col} should be a FULL UNIQUE (no partial predicate); got: {indexdef}"
        )


def test_game_states_has_lookup_plus_partial_unique(db_pool: Any) -> None:
    """game_states has non-unique lookup btree + partial UNIQUE (current rows)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'game_states'
              AND indexname IN (
                  'idx_game_states_game_state_key',
                  'idx_game_states_game_state_key_current'
              )
            ORDER BY indexname
            """
        )
        rows = cur.fetchall()
    index_defs = {r["indexname"]: r["indexdef"] for r in rows}

    # Lookup btree: non-unique, no partial predicate.
    lookup = index_defs.get("idx_game_states_game_state_key")
    assert lookup is not None, "Missing lookup btree on game_states.game_state_key"
    assert "UNIQUE" not in lookup, "Lookup btree must NOT be UNIQUE"

    # Partial UNIQUE: SCD2-aware, fires only on current rows.
    partial = index_defs.get("idx_game_states_game_state_key_current")
    assert partial is not None, "Missing partial UNIQUE on game_states.game_state_key"
    assert "UNIQUE" in partial, "Partial index must be UNIQUE"
    assert "row_current_ind = true" in partial, (
        "Partial UNIQUE must filter on row_current_ind = true (SCD2 contract)"
    )


# =============================================================================
# Group 3: Backfill format (<PREFIX>-<id>)
# =============================================================================


@pytest.mark.parametrize(("table", "key_col", "prefix", "is_scd2"), _KEY_SPEC)
def test_backfill_matches_prefix_pattern(
    db_pool: Any, table: str, key_col: str, prefix: str, is_scd2: bool
) -> None:
    """Every existing row has ``<PREFIX>-<id>`` or a canonical downstream value.

    Post-migration, all rows should carry a key in one of these shapes:
      * ``<PREFIX>-<id>`` — the backfilled format
      * ``<PREFIX>-<id>`` produced by CRUD after the migration
    No TEMP- values should ever be observable (they are replaced in-txn).
    """
    # safe: table/key_col are hardcoded in _KEY_SPEC
    with get_cursor() as cur:
        # First: no TEMP- values must be externally visible.
        cur.execute(
            f"SELECT COUNT(*) AS c FROM {table} WHERE {key_col} LIKE 'TEMP-%%'"  # noqa: S608
        )
        temp_count = int(cur.fetchone()["c"])
        assert temp_count == 0, (
            f"{table}.{key_col} has {temp_count} TEMP- sentinels — "
            f"two-step INSERT pattern is not atomic (transaction boundary bug)"
        )

        # Spot-check format on a sample (bounded to avoid megatable scans).
        # game_states has ~29k rows — LIMIT 100 is plenty.
        cur.execute(
            f"SELECT id, {key_col} FROM {table} "  # noqa: S608
            f"ORDER BY id LIMIT 100"
        )
        rows = cur.fetchall()
    for row in rows:
        expected = f"{prefix}-{row['id']}"
        assert row[key_col] == expected, (
            f"{table}.{key_col} for id={row['id']} is {row[key_col]!r}, expected {expected!r}"
        )


# =============================================================================
# Group 4: CRUD create paths produce canonical keys
# =============================================================================


def test_create_market_assigns_canonical_market_key(db_pool: Any) -> None:
    """``create_market`` inserts with TEMP and rewrites to ``MKT-{id}``."""
    from tests.fixtures.cleanup_helpers import delete_market_with_children

    test_ticker = f"TEST-0062-MKT-{uuid.uuid4().hex[:8]}"
    with get_cursor(commit=True) as cur:
        delete_market_with_children(cur, "ticker = %s", (test_ticker,))

    market_pk = create_market(
        platform_id="kalshi",
        event_id=None,
        external_id=f"{test_ticker}-EXT",
        ticker=test_ticker,
        title="Test market for 0062 key format",
        yes_ask_price=Decimal("0.5000"),
        no_ask_price=Decimal("0.5000"),
    )
    try:
        with get_cursor() as cur:
            cur.execute("SELECT market_key FROM markets WHERE id = %s", (market_pk,))
            row = cur.fetchone()
        assert row is not None
        assert row["market_key"] == f"MKT-{market_pk}"
    finally:
        with get_cursor(commit=True) as cur:
            delete_market_with_children(cur, "ticker = %s", (test_ticker,))


def test_create_event_assigns_canonical_event_key(db_pool: Any) -> None:
    """``create_event`` inserts with TEMP and rewrites to ``EVT-{id}``."""
    from tests.fixtures.cleanup_helpers import delete_event_with_children

    test_ext = f"TEST-0062-EVT-{uuid.uuid4().hex[:8]}"
    with get_cursor(commit=True) as cur:
        delete_event_with_children(cur, "external_id = %s", (test_ext,))

    event_pk = create_event(
        event_id=test_ext,
        platform_id="kalshi",
        external_id=test_ext,
        category="sports",
        title="Test event for 0062 key format",
    )
    try:
        with get_cursor() as cur:
            cur.execute("SELECT event_key FROM events WHERE id = %s", (event_pk,))
            row = cur.fetchone()
        assert row is not None
        assert row["event_key"] == f"EVT-{event_pk}"
    finally:
        with get_cursor(commit=True) as cur:
            delete_event_with_children(cur, "external_id = %s", (test_ext,))


def test_create_game_state_assigns_canonical_game_state_key(db_pool: Any) -> None:
    """``create_game_state`` inserts with TEMP and rewrites to ``GST-{id}``."""
    espn_event_id = f"TEST-0062-GST-{uuid.uuid4().hex[:8]}"
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM game_states WHERE espn_event_id = %s",
            (espn_event_id,),
        )

    state_id = create_game_state(
        espn_event_id=espn_event_id,
        league="nfl",
        game_status="pre",
    )
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT game_state_key FROM game_states WHERE id = %s",
                (state_id,),
            )
            row = cur.fetchone()
        assert row is not None
        assert row["game_state_key"] == f"GST-{state_id}"
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM game_states WHERE espn_event_id = %s",
                (espn_event_id,),
            )


# =============================================================================
# Group 5: **Critical SCD2 contract** — upsert carries key forward
# =============================================================================


def test_upsert_game_state_carries_key_forward_on_supersede(db_pool: Any) -> None:
    """Regression guard: SCD supersede must preserve game_state_key.

    This is the load-bearing test for migration 0062.  ``upsert_game_state``
    is the hot SCD2 path (~190 calls/live game).  On supersede, the new
    row MUST carry the same ``game_state_key`` as the CLOSED row — a
    regeneration would fork the logical-entity identity across versions,
    breaking every downstream consumer that joins across SCD history.

    Shape:
        - First upsert (no current row): INSERT path assigns GST-{id}.
        - Second upsert (score change): SUPERSEDE path closes the old
          row and inserts a new one.  Assert both rows share the same
          game_state_key.
    """
    espn_event_id = f"TEST-0062-SCD-{uuid.uuid4().hex[:8]}"
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM game_states WHERE espn_event_id = %s",
            (espn_event_id,),
        )

    try:
        # First upsert: first-insert path.  Assigns a fresh GST-{id}.
        first_id = upsert_game_state(
            espn_event_id=espn_event_id,
            home_score=0,
            away_score=0,
            period=0,
            game_status="pre",
            league="nfl",
        )
        assert first_id is not None, "First upsert should have inserted"

        with get_cursor() as cur:
            cur.execute(
                "SELECT game_state_key FROM game_states WHERE id = %s",
                (first_id,),
            )
            original_key = cur.fetchone()["game_state_key"]
        assert original_key == f"GST-{first_id}", "First-insert path must assign canonical GST-{id}"

        # Second upsert: supersede path (score changed).
        second_id = upsert_game_state(
            espn_event_id=espn_event_id,
            home_score=7,
            away_score=0,
            period=1,
            game_status="in_progress",
            league="nfl",
        )
        assert second_id is not None, "Score change must create a new version"
        assert second_id != first_id, "New version must get a new surrogate id"

        # Assert SCD state: exactly 2 rows for this espn_event_id, both
        # carrying the same game_state_key (the one assigned at first-insert).
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT id, game_state_key, row_current_ind
                FROM game_states
                WHERE espn_event_id = %s
                ORDER BY id
                """,
                (espn_event_id,),
            )
            rows = cur.fetchall()
        assert len(rows) == 2, f"Expected 2 SCD rows, got {len(rows)}"
        assert all(r["game_state_key"] == original_key for r in rows), (
            f"SCD copy-forward broken: keys diverged across versions: "
            f"{[(r['id'], r['game_state_key'], r['row_current_ind']) for r in rows]}"
        )
        # Sanity: historical row is closed, new row is current.
        historical = next(r for r in rows if r["id"] == first_id)
        current = next(r for r in rows if r["id"] == second_id)
        assert historical["row_current_ind"] is False
        assert current["row_current_ind"] is True
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM game_states WHERE espn_event_id = %s",
                (espn_event_id,),
            )


# =============================================================================
# Group 6: get_or_create_game — CREATE + CONFLICT branches
# =============================================================================


def test_get_or_create_game_create_path_assigns_canonical_key(db_pool: Any) -> None:
    """CREATE branch produces ``GAM-{id}``; no TEMP value leaks out."""
    # Unique matchup to force the CREATE branch.
    suffix = uuid.uuid4().hex[:6].upper()
    home = f"T{suffix[:2]}H"
    away = f"T{suffix[2:4]}A"
    game_date_val = date(2099, 1, 1)

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM games WHERE sport = 'football' "
            "AND home_team_code = %s AND away_team_code = %s",
            (home, away),
        )

    try:
        game_id = get_or_create_game(
            sport="football",
            game_date=game_date_val,
            home_team_code=home,
            away_team_code=away,
            season=2099,
            league="nfl",
        )
        with get_cursor() as cur:
            cur.execute("SELECT game_key FROM games WHERE id = %s", (game_id,))
            row = cur.fetchone()
        assert row["game_key"] == f"GAM-{game_id}", (
            f"CREATE path must assign GAM-{{id}}; got {row['game_key']!r}"
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM games WHERE sport = 'football' "
                "AND home_team_code = %s AND away_team_code = %s",
                (home, away),
            )


def test_get_or_create_game_conflict_path_preserves_existing_key(db_pool: Any) -> None:
    """CONFLICT branch does NOT overwrite the existing game_key."""
    suffix = uuid.uuid4().hex[:6].upper()
    home = f"T{suffix[:2]}C"
    away = f"T{suffix[2:4]}D"
    game_date_val = date(2099, 1, 2)

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM games WHERE sport = 'football' "
            "AND home_team_code = %s AND away_team_code = %s",
            (home, away),
        )

    try:
        # First call: creates the row.
        first_id = get_or_create_game(
            sport="football",
            game_date=game_date_val,
            home_team_code=home,
            away_team_code=away,
            season=2099,
            league="nfl",
        )
        with get_cursor() as cur:
            cur.execute("SELECT game_key FROM games WHERE id = %s", (first_id,))
            original_key = cur.fetchone()["game_key"]

        # Second call: hits ON CONFLICT, must NOT change game_key.
        second_id = get_or_create_game(
            sport="football",
            game_date=game_date_val,
            home_team_code=home,
            away_team_code=away,
            season=2099,
            league="nfl",
            home_score=14,
            away_score=7,
            game_status="final",
        )
        assert second_id == first_id, "CONFLICT path must return the same id"

        with get_cursor() as cur:
            cur.execute("SELECT game_key FROM games WHERE id = %s", (first_id,))
            post_key = cur.fetchone()["game_key"]
        assert post_key == original_key, (
            f"ON CONFLICT path must preserve game_key: was {original_key!r}, now {post_key!r}"
        )
        # Sanity: no TEMP sentinel leaked into the row.
        assert not post_key.startswith("TEMP-"), (
            f"TEMP sentinel leaked through CONFLICT path: {post_key!r}"
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM games WHERE sport = 'football' "
                "AND home_team_code = %s AND away_team_code = %s",
                (home, away),
            )


# =============================================================================
# Group 7: historical_games batch loader
# =============================================================================


def test_historical_games_batch_loader_assigns_canonical_keys(db_pool: Any) -> None:
    """Batch-inserted games all end up with ``GAM-<id>`` (no TEMP leaks)."""
    from precog.database.seeding.historical_games_loader import _flush_games_batch

    suffix = uuid.uuid4().hex[:6].upper()
    # Two rows with distinct natural keys — both hit the INSERT branch.
    home1 = f"T{suffix[:2]}E"
    away1 = f"T{suffix[2:4]}F"
    home2 = f"T{suffix[:2]}G"
    away2 = f"T{suffix[2:4]}H"

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM games WHERE home_team_code = ANY(%s)",
            ([home1, home2],),
        )

    # Look up real sport_id + league_id via CRUD helpers BEFORE building
    # the tuples (Glokta S60 review W4: eliminates fragile ``row[:-3]``
    # tuple-slicing patch that was tightly coupled to the batch tuple
    # column order).
    from precog.database.crud_lookups import get_league_id, get_sport_id

    sport_id = get_sport_id("football")
    league_id = get_league_id("nfl")

    try:
        # Build a minimal batch mirroring the tuple shape in
        # historical_games_loader.bulk_insert_historical_games.  The TEMP
        # sentinel is the last field; sport_id + league_id are the two
        # fields immediately before it.
        batch = [
            (
                "football",  # sport
                2099,  # season
                date(2099, 2, 1),  # game_date
                home1,
                away1,
                None,  # home_team_id
                None,  # away_team_id
                21,  # home_score
                14,  # away_score
                False,  # neutral_site
                False,  # is_playoff
                "regular",  # game_type
                None,  # venue_name
                "fivethirtyeight",  # data_source
                None,  # source_file
                None,  # external_game_id
                "nfl",  # league
                "final",  # game_status
                sport_id,  # sport_id (NOT NULL as of 0061)
                league_id,  # league_id
                f"TEMP-{uuid.uuid4()}",  # game_key sentinel
            ),
            (
                "football",
                2099,
                date(2099, 2, 2),
                home2,
                away2,
                None,
                None,
                28,
                24,
                False,
                False,
                "regular",
                None,
                "fivethirtyeight",
                None,
                None,
                "nfl",
                "final",
                sport_id,
                league_id,
                f"TEMP-{uuid.uuid4()}",
            ),
        ]

        _flush_games_batch(batch)

        with get_cursor() as cur:
            cur.execute(
                "SELECT id, game_key FROM games WHERE home_team_code = ANY(%s) ORDER BY id",
                ([home1, home2],),
            )
            rows = cur.fetchall()
        assert len(rows) == 2, "Both rows should have inserted"
        for row in rows:
            assert row["game_key"] == f"GAM-{row['id']}", (
                f"Batch INSERT path must rewrite TEMP to GAM-{{id}}; got {row['game_key']!r}"
            )
            assert not row["game_key"].startswith("TEMP-"), "TEMP sentinel leaked out of batch path"
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM games WHERE home_team_code = ANY(%s)",
                ([home1, home2],),
            )


# =============================================================================
# Group 8: Uniqueness is enforced
# =============================================================================


def test_markets_market_key_full_unique_enforced(db_pool: Any) -> None:
    """A duplicate market_key on markets must raise IntegrityError."""
    from tests.fixtures.cleanup_helpers import delete_market_with_children

    test_ticker1 = f"TEST-0062-UQ1-{uuid.uuid4().hex[:8]}"
    test_ticker2 = f"TEST-0062-UQ2-{uuid.uuid4().hex[:8]}"
    with get_cursor(commit=True) as cur:
        delete_market_with_children(cur, "ticker = %s", (test_ticker1,))
        delete_market_with_children(cur, "ticker = %s", (test_ticker2,))

    try:
        pk1 = create_market(
            platform_id="kalshi",
            event_id=None,
            external_id=f"{test_ticker1}-EXT",
            ticker=test_ticker1,
            title="0062 uniqueness test row 1",
            yes_ask_price=Decimal("0.5000"),
            no_ask_price=Decimal("0.5000"),
        )
        # Create a second market, then try to force-overwrite its market_key
        # to the first row's value.  The partial UNIQUE should reject.
        pk2 = create_market(
            platform_id="kalshi",
            event_id=None,
            external_id=f"{test_ticker2}-EXT",
            ticker=test_ticker2,
            title="0062 uniqueness test row 2",
            yes_ask_price=Decimal("0.5000"),
            no_ask_price=Decimal("0.5000"),
        )
        with pytest.raises(psycopg2.errors.UniqueViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE markets SET market_key = %s WHERE id = %s",
                    (f"MKT-{pk1}", pk2),
                )
    finally:
        with get_cursor(commit=True) as cur:
            delete_market_with_children(cur, "ticker = %s", (test_ticker1,))
            delete_market_with_children(cur, "ticker = %s", (test_ticker2,))


def test_game_states_partial_unique_allows_historical_duplicates(db_pool: Any) -> None:
    """Partial UNIQUE on game_states.game_state_key permits historical dups.

    This tests the SCD2-aware index: two rows can share the same
    ``game_state_key`` as long as at most ONE has ``row_current_ind = TRUE``.
    After an ``upsert_game_state`` supersede, exactly this situation exists
    (old row: key=X, current=FALSE; new row: key=X, current=TRUE).
    """
    espn_event_id = f"TEST-0062-UQP-{uuid.uuid4().hex[:8]}"
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM game_states WHERE espn_event_id = %s",
            (espn_event_id,),
        )
    try:
        # Do a real supersede — this is the production shape of the partial UNIQUE.
        upsert_game_state(
            espn_event_id=espn_event_id,
            home_score=0,
            away_score=0,
            period=0,
            game_status="pre",
            league="nfl",
        )
        upsert_game_state(
            espn_event_id=espn_event_id,
            home_score=7,
            away_score=0,
            period=1,
            game_status="in_progress",
            league="nfl",
        )
        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS c FROM game_states WHERE espn_event_id = %s",
                (espn_event_id,),
            )
            total = int(cur.fetchone()["c"])
            cur.execute(
                "SELECT COUNT(*) AS c FROM game_states "
                "WHERE espn_event_id = %s AND row_current_ind = TRUE",
                (espn_event_id,),
            )
            current = int(cur.fetchone()["c"])
        assert total == 2, "SCD2 supersede should have produced 2 rows"
        assert current == 1, (
            "Partial UNIQUE WHERE row_current_ind=TRUE must allow exactly "
            "one current row per game_state_key"
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM game_states WHERE espn_event_id = %s",
                (espn_event_id,),
            )
