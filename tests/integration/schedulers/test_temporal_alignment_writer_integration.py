"""Integration tests for temporal_alignment_writer (#896, part of #887 arc).

Module under test: src/precog/schedulers/temporal_alignment_writer.py

Policy: integration tier -- real precog_test DB, no mocks. Tests exercise
the REAL FK chain (market_snapshots -> markets -> events -> games <-
game_states) through the production _UNALIGNED_QUERY and
insert_temporal_alignment_batch. Unit-level concerns (quality threshold
tables, query-to-dict transformation) already live in
``tests/unit/schedulers/test_temporal_alignment_writer.py`` and are NOT
duplicated here.

This is the first of 7 missing test types for this module; subsequent
types (e2e, property, stress, race, security, performance, chaos) will
follow the same fixture + cleanup conventions established here.

Related:
    - Issue #896 (missing business-tier coverage arc for writer)
    - Issue #887 (parent audit that surfaced the gap)
    - Issue #722 (URGENT data loss per unplayed game -- writer origin)
    - Epic #745 (Schema Hardening Arc, Cohort C0)
    - Glokta review B1: writer MUST NOT filter row_current_ind; in SCD
      Type 2 a snapshot becomes non-current every ~15s, so a one-cycle
      writer lag would orphan non-current snapshots permanently.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg2
import pytest

from precog.database.connection import get_cursor
from precog.schedulers.temporal_alignment_writer import (
    create_temporal_alignment_writer,
)

pytestmark = [pytest.mark.integration]

# Unique business-key prefix keeps this file's fixture data disjoint
# from other integration tests that may be seeding similar tables.
_PREFIX = "TEMPALI"


# =============================================================================
# Fixture helpers -- raw-SQL inserts that give us explicit control over
# row_start_ts. The production CRUD helpers all stamp NOW(), which would
# make lookback-window and SCD-ordering tests impossible to write
# deterministically.
# =============================================================================


def _insert_game_state(
    cur: Any,
    *,
    espn_event_id: str,
    league_id: int,
    game_id: int,
    row_start_ts: datetime,
    row_current_ind: bool = True,
    row_end_ts: datetime | None = None,
    game_status: str = "in_progress",
    home_score: int = 7,
    away_score: int = 3,
    period: int = 1,
    clock_display: str = "10:00",
) -> int:
    """Insert a game_states row with an explicitly controlled row_start_ts.

    Mirrors the production INSERT in ``crud_game_states.create_game_state``
    including the Migration 0062 two-step ``TEMP-{uuid}`` sentinel rewrite,
    because ``game_state_key`` is NOT NULL with a partial UNIQUE index on
    ``WHERE row_current_ind = TRUE``.
    """
    temp_key = f"TEMP-{uuid.uuid4()}"
    cur.execute(
        """
        INSERT INTO game_states (
            espn_event_id, home_score, away_score, period, game_status,
            league, league_id, data_source, game_id, game_state_key,
            row_current_ind, row_start_ts, row_end_ts, clock_display,
            neutral_site
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
        RETURNING id
        """,
        (
            espn_event_id,
            home_score,
            away_score,
            period,
            game_status,
            "nfl",
            league_id,
            "espn",
            game_id,
            temp_key,
            row_current_ind,
            row_start_ts,
            row_end_ts,
            clock_display,
        ),
    )
    gs_id = cur.fetchone()["id"]
    cur.execute(
        "UPDATE game_states SET game_state_key = %s WHERE id = %s",
        (f"GST-{gs_id}", gs_id),
    )
    return int(gs_id)


def _insert_market_snapshot(
    cur: Any,
    *,
    market_id: int,
    row_start_ts: datetime,
    row_current_ind: bool = True,
    row_end_ts: datetime | None = None,
    yes_ask_price: Decimal = Decimal("0.5200"),
    no_ask_price: Decimal = Decimal("0.4800"),
    spread: Decimal | None = Decimal("0.0100"),
    volume: int = 100,
) -> int:
    """Insert a market_snapshots row with explicitly controlled row_start_ts."""
    cur.execute(
        """
        INSERT INTO market_snapshots (
            market_id, yes_ask_price, no_ask_price, spread, volume,
            row_current_ind, row_start_ts, row_end_ts
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            market_id,
            yes_ask_price,
            no_ask_price,
            spread,
            volume,
            row_current_ind,
            row_start_ts,
            row_end_ts,
        ),
    )
    return int(cur.fetchone()["id"])


# =============================================================================
# Module-scoped FK parent chain -- one set of platform/sport/league/teams/
# venue/game/event/market per test session to avoid paying that cost 7x.
# =============================================================================


@pytest.fixture
def fk_chain() -> Any:
    """Create the full FK parent chain for this test's market_snapshots
    and game_states rows. Yields a dict of the created IDs. Tears down
    every row on exit (strict reverse FK order; RESTRICT semantics).
    """
    # Use a per-test unique suffix so concurrent xdist workers don't
    # collide on business keys (ticker, external_id, espn_event_id).
    # Short suffix (4 hex) because team_code is varchar(10); longer
    # suffix-prefixed codes like "TEMPALI-H1234" exceed the limit.
    suffix_long = uuid.uuid4().hex[:8]
    suffix_short = suffix_long[:4]
    espn_event_id = f"{_PREFIX}-ESPN-{suffix_long}"
    # team_code varchar(10): "TH"+4hex=6 chars.
    team_home_code = f"TH{suffix_short}"
    team_away_code = f"TA{suffix_short}"
    team_home_id = 90000 + (int(suffix_long, 16) % 9000)
    team_away_id = team_home_id + 1
    # Offset by 1 prevents collision within the same test; xdist isolation
    # handled by the suffix randomization above.

    with get_cursor(commit=True) as cur:
        # Seed NFL league_id/sport_id exist by precog_test default (verified
        # via MCP: sports=6 rows, leagues=11 rows). Look them up vs assume.
        cur.execute("SELECT id FROM sports WHERE sport_key = 'football'")
        sport_id = cur.fetchone()["id"]
        cur.execute("SELECT id FROM leagues WHERE league_key = 'nfl'")
        league_id = cur.fetchone()["id"]

        # Platform -- reuse existing test_platform if present.
        cur.execute(
            """
            INSERT INTO platforms (platform_id, platform_type, display_name, base_url, status)
            VALUES ('test_platform', 'trading', 'Test Platform', 'https://test.example.com', 'active')
            ON CONFLICT (platform_id) DO NOTHING
            """
        )

        # Teams (need 2: home + away).
        cur.execute(
            """
            INSERT INTO teams (
                team_id, team_code, team_name, sport, league,
                sport_id, league_id, current_elo_rating
            )
            VALUES (%s, %s, %s, 'football', 'nfl', %s, %s, 1500),
                   (%s, %s, %s, 'football', 'nfl', %s, %s, 1500)
            ON CONFLICT (team_id) DO NOTHING
            """,
            (
                team_home_id,
                team_home_code,
                f"Test Home {suffix_long}",
                sport_id,
                league_id,
                team_away_id,
                team_away_code,
                f"Test Away {suffix_long}",
                sport_id,
                league_id,
            ),
        )

        # Venue (optional FK, but clean fixture pattern).
        cur.execute(
            """
            INSERT INTO venues (espn_venue_id, venue_name, city, state, indoor)
            VALUES (%s, %s, 'Test City', 'TS', FALSE)
            RETURNING venue_id
            """,
            (f"{_PREFIX}-V-{suffix_long}", f"Test Stadium {suffix_long}"),
        )
        venue_id = cur.fetchone()["venue_id"]

        # Game (required parent -- events.game_id FK).
        cur.execute(
            """
            INSERT INTO games (
                sport, game_date, home_team_code, away_team_code, season,
                league, home_team_id, away_team_id, venue_id,
                neutral_site, is_playoff, game_status, espn_event_id,
                data_source, sport_id, league_id, game_key
            )
            VALUES (
                'football', CURRENT_DATE, %s, %s, 2026,
                'nfl', %s, %s, %s,
                FALSE, FALSE, 'scheduled', %s,
                'espn', %s, %s, %s
            )
            RETURNING id
            """,
            (
                team_home_code,
                team_away_code,
                team_home_id,
                team_away_id,
                venue_id,
                espn_event_id,
                sport_id,
                league_id,
                f"GAME-{_PREFIX}-{suffix_long}",
            ),
        )
        game_id = cur.fetchone()["id"]

        # Event (connects market back to game via markets.event_id ->
        # events.id, and e.game_id -> games.id per the production query).
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
                f"{_PREFIX}-EVT-{suffix_long}",
                f"Test Event {suffix_long}",
                game_id,
                f"EVT-{_PREFIX}-{suffix_long}",
            ),
        )
        event_id = cur.fetchone()["id"]

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
                f"{_PREFIX}-EXT-{suffix_long}",
                f"{_PREFIX}-MKT-{suffix_long}",
                f"Test Market {suffix_long}",
                f"MKT-{_PREFIX}-{suffix_long}",
            ),
        )
        market_id = cur.fetchone()["id"]

    ids = {
        "sport_id": sport_id,
        "league_id": league_id,
        "team_home_id": team_home_id,
        "team_away_id": team_away_id,
        "venue_id": venue_id,
        "game_id": game_id,
        "event_id": event_id,
        "market_id": market_id,
        "espn_event_id": espn_event_id,
        "suffix": suffix_long,
        "team_home_code": team_home_code,
        "team_away_code": team_away_code,
    }

    yield ids

    # Teardown in strict reverse FK order (RESTRICT semantics throughout
    # post-migration 0057). Children -> parents, deepest first.
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM temporal_alignment WHERE market_id = %s", (market_id,))
        cur.execute("DELETE FROM market_snapshots WHERE market_id = %s", (market_id,))
        cur.execute("DELETE FROM markets WHERE id = %s", (market_id,))
        cur.execute("DELETE FROM game_states WHERE game_id = %s", (game_id,))
        cur.execute("DELETE FROM events WHERE id = %s", (event_id,))
        cur.execute("DELETE FROM games WHERE id = %s", (game_id,))
        cur.execute("DELETE FROM venues WHERE venue_id = %s", (venue_id,))
        cur.execute(
            "DELETE FROM teams WHERE team_id IN (%s, %s)",
            (team_home_id, team_away_id),
        )


# =============================================================================
# Integration Tests
# =============================================================================


class TestTemporalAlignmentWriterIntegration:
    """End-to-end integration tests against precog_test."""

    def test_happy_path_alignment_produces_good_quality(self, fk_chain: dict[str, Any]) -> None:
        """Writer creates one alignment row with quality='good' for a ~5s delta."""
        now = datetime.now(tz=UTC)
        with get_cursor(commit=True) as cur:
            ms_id = _insert_market_snapshot(
                cur,
                market_id=fk_chain["market_id"],
                row_start_ts=now - timedelta(seconds=60),
            )
            gs_id = _insert_game_state(
                cur,
                espn_event_id=fk_chain["espn_event_id"],
                league_id=fk_chain["league_id"],
                game_id=fk_chain["game_id"],
                row_start_ts=now - timedelta(seconds=55),
            )

        writer = create_temporal_alignment_writer(
            poll_interval=30,
            lookback_seconds=600,
            batch_limit=1000,
        )
        # Under xdist we cannot assert on the global items_created counter
        # (other workers' unaligned snapshots fall inside the same
        # lookback window). Assert only on rows the writer produced for
        # THIS test's market_id, which is unique per fk_chain.
        writer._poll_once()

        with get_cursor() as cur:
            cur.execute(
                """
                SELECT alignment_quality, time_delta_seconds
                FROM temporal_alignment
                WHERE market_snapshot_id = %s AND game_state_id = %s
                """,
                (ms_id, gs_id),
            )
            rows = cur.fetchall()

        assert len(rows) == 1
        assert rows[0]["alignment_quality"] == "good"
        # 5s delta must land within 'good' tier (1 < d <= 15).
        assert Decimal("1") < rows[0]["time_delta_seconds"] <= Decimal("15")

    def test_quality_boundary_classification_across_tiers(self, fk_chain: dict[str, Any]) -> None:
        """Deltas 0.5s / 10s / 45s / 90s -> exact / good / fair / poor."""
        now = datetime.now(tz=UTC)
        # Each pair needs its OWN game_state (the LATERAL subquery returns
        # the *closest* gs per snapshot; without per-pair gs rows the
        # closest match would collapse to one).
        expected = [
            (Decimal("0.5"), "exact"),
            (Decimal("10"), "good"),
            (Decimal("45"), "fair"),
            (Decimal("90"), "poor"),
        ]

        pair_ids: list[tuple[int, int, str]] = []
        with get_cursor(commit=True) as cur:
            for i, (delta_s, quality) in enumerate(expected):
                # Anchors spaced 150s apart (30, 180, 330, 480 seconds ago)
                # so each snapshot's LATERAL-closest gs is unambiguously
                # its own intended partner, not a neighbor's gs. The
                # max delta (90s for "poor") plus 60s headroom fits
                # inside 150s spacing. All 4 anchors stay inside the
                # 600s lookback window. Per-pair espn_event_id keeps
                # the partial UNIQUE on game_states satisfied.
                anchor = now - timedelta(seconds=30 + i * 150)
                # Only the FIRST pair stays current; older ones flip to
                # row_current_ind=FALSE. Both market_snapshots and
                # game_states have partial UNIQUE indexes on (business
                # key) WHERE row_current_ind=TRUE. This does NOT contradict
                # the writer's contract -- find_unaligned_pairs must still
                # align non-current snapshots (Glokta B1). The test simply
                # respects the DB's uniqueness invariant while still
                # exercising the writer's quality classification across
                # the full range of deltas.
                ms_id = _insert_market_snapshot(
                    cur,
                    market_id=fk_chain["market_id"],
                    row_start_ts=anchor,
                    row_current_ind=(i == 0),
                    row_end_ts=None if i == 0 else anchor + timedelta(seconds=1),
                )
                gs_id = _insert_game_state(
                    cur,
                    espn_event_id=f"{fk_chain['espn_event_id']}-b{i}",
                    league_id=fk_chain["league_id"],
                    game_id=fk_chain["game_id"],
                    row_start_ts=anchor - timedelta(seconds=float(delta_s)),
                    row_current_ind=(i == 0),
                    row_end_ts=None if i == 0 else anchor,
                )
                pair_ids.append((ms_id, gs_id, quality))

        writer = create_temporal_alignment_writer(lookback_seconds=600, batch_limit=1000)
        writer._poll_once()
        # Scope assertions to THIS test's market_id -- parallel xdist
        # workers may add other unaligned pairs inside the same cycle
        # and inflate the global items_created counter.

        with get_cursor() as cur:
            cur.execute(
                """
                SELECT market_snapshot_id, alignment_quality
                FROM temporal_alignment
                WHERE market_id = %s
                """,
                (fk_chain["market_id"],),
            )
            rows = {r["market_snapshot_id"]: r["alignment_quality"] for r in cur.fetchall()}

        assert len(rows) == 4
        for ms_id, _, quality in pair_ids:
            assert rows.get(ms_id) == quality, (
                f"snapshot {ms_id}: expected quality {quality!r}, got {rows.get(ms_id)!r}"
            )

    def test_stale_snapshot_outside_lookback_not_aligned(self, fk_chain: dict[str, Any]) -> None:
        """Snapshot with row_start_ts older than _LOOKBACK_SECONDS is skipped."""
        now = datetime.now(tz=UTC)
        with get_cursor(commit=True) as cur:
            # 700s old -- outside default 600s lookback.
            stale_ms_id = _insert_market_snapshot(
                cur,
                market_id=fk_chain["market_id"],
                row_start_ts=now - timedelta(seconds=700),
                row_current_ind=False,
                row_end_ts=now - timedelta(seconds=60),
            )
            _insert_game_state(
                cur,
                espn_event_id=fk_chain["espn_event_id"],
                league_id=fk_chain["league_id"],
                game_id=fk_chain["game_id"],
                row_start_ts=now - timedelta(seconds=695),
            )

        writer = create_temporal_alignment_writer(lookback_seconds=600, batch_limit=1000)
        writer._poll_once()
        # Scope the assertion to THIS test's snapshot -- other xdist
        # workers may have produced alignments this cycle.

        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM temporal_alignment WHERE market_snapshot_id = %s",
                (stale_ms_id,),
            )
            assert cur.fetchone()["n"] == 0

    def test_idempotence_no_duplicate_rows_on_rerun(self, fk_chain: dict[str, Any]) -> None:
        """Second poll over unchanged data inserts zero net-new rows."""
        now = datetime.now(tz=UTC)
        with get_cursor(commit=True) as cur:
            _insert_market_snapshot(
                cur,
                market_id=fk_chain["market_id"],
                row_start_ts=now - timedelta(seconds=30),
            )
            _insert_game_state(
                cur,
                espn_event_id=fk_chain["espn_event_id"],
                league_id=fk_chain["league_id"],
                game_id=fk_chain["game_id"],
                row_start_ts=now - timedelta(seconds=29),
            )

        writer = create_temporal_alignment_writer(batch_limit=1000)

        writer._poll_once()
        # Count per-market BEFORE the second poll; xdist-safe scope.
        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM temporal_alignment WHERE market_id = %s",
                (fk_chain["market_id"],),
            )
            count_after_first = cur.fetchone()["n"]

        writer._poll_once()
        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM temporal_alignment WHERE market_id = %s",
                (fk_chain["market_id"],),
            )
            count_after_second = cur.fetchone()["n"]

        assert count_after_first == 1
        # Idempotence: second poll MUST NOT add any new rows for
        # this market.
        assert count_after_second == count_after_first

    def test_scd_type_2_non_current_snapshots_aligned(self, fk_chain: dict[str, Any]) -> None:
        """Glokta invariant B1: the writer MUST NOT filter row_current_ind.

        Both a non-current (superseded) snapshot and the current one must
        receive temporal_alignment rows, because in SCD Type 2 a snapshot
        goes non-current every ~15s -- filtering row_current_ind would
        orphan snapshots whenever the writer falls even one cycle behind.
        """
        now = datetime.now(tz=UTC)
        with get_cursor(commit=True) as cur:
            # Older (non-current) snapshot.
            non_current_ms = _insert_market_snapshot(
                cur,
                market_id=fk_chain["market_id"],
                row_start_ts=now - timedelta(seconds=40),
                row_current_ind=False,
                row_end_ts=now - timedelta(seconds=20),
            )
            # Newer (current) snapshot.
            current_ms = _insert_market_snapshot(
                cur,
                market_id=fk_chain["market_id"],
                row_start_ts=now - timedelta(seconds=20),
                row_current_ind=True,
            )
            # A single game_state that's within reach of both.
            _insert_game_state(
                cur,
                espn_event_id=fk_chain["espn_event_id"],
                league_id=fk_chain["league_id"],
                game_id=fk_chain["game_id"],
                row_start_ts=now - timedelta(seconds=25),
            )

        writer = create_temporal_alignment_writer(batch_limit=1000)
        writer._poll_once()
        # Both snapshots align against the same game_state via the
        # LATERAL "closest" subquery. Scope to THIS test's market_id
        # for xdist-safe assertion.

        with get_cursor() as cur:
            cur.execute(
                """
                SELECT market_snapshot_id
                FROM temporal_alignment
                WHERE market_id = %s
                """,
                (fk_chain["market_id"],),
            )
            aligned_ms_ids = {r["market_snapshot_id"] for r in cur.fetchall()}

        assert non_current_ms in aligned_ms_ids, (
            "non-current snapshot was not aligned -- row_current_ind filter "
            "has been incorrectly re-introduced somewhere in the query (B1)"
        )
        assert current_ms in aligned_ms_ids

    def test_batch_limit_honored_across_cycles(self, fk_chain: dict[str, Any]) -> None:
        """batch_limit caps inserts per cycle; remainder processed next cycle.

        Uses batch_limit=10 with 15 pairs rather than the production
        1000/1100 for CI speed -- semantically identical, 100x faster.
        """
        now = datetime.now(tz=UTC)
        total_pairs = 15
        batch_limit = 10

        with get_cursor(commit=True) as cur:
            for i in range(total_pairs):
                anchor = now - timedelta(seconds=30 + i * 20)
                _insert_market_snapshot(
                    cur,
                    market_id=fk_chain["market_id"],
                    row_start_ts=anchor,
                    row_current_ind=(i == 0),
                    row_end_ts=None if i == 0 else anchor + timedelta(seconds=10),
                )
                _insert_game_state(
                    cur,
                    espn_event_id=f"{fk_chain['espn_event_id']}-b{i}",
                    league_id=fk_chain["league_id"],
                    game_id=fk_chain["game_id"],
                    row_start_ts=anchor - timedelta(seconds=2),
                    row_current_ind=(i == 0),
                    row_end_ts=None if i == 0 else anchor,
                )

        writer = create_temporal_alignment_writer(batch_limit=batch_limit)

        writer._poll_once()
        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM temporal_alignment WHERE market_id = %s",
                (fk_chain["market_id"],),
            )
            count_after_first = cur.fetchone()["n"]

        # Batch limit enforced EXACTLY: the writer instance's batch_limit
        # is a per-instance cap and each xdist worker operates on its own
        # per-test market_id (see fk_chain fixture), so the first poll
        # must align exactly batch_limit pairs — no xdist contention.
        assert count_after_first == batch_limit, (
            f"batch_limit={batch_limit} not honored exactly: "
            f"first poll aligned {count_after_first}/{total_pairs} pairs"
        )

        writer._poll_once()
        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM temporal_alignment WHERE market_id = %s",
                (fk_chain["market_id"],),
            )
            count_after_second = cur.fetchone()["n"]

        # Two cycles of batch_limit=10 cover all 15 pairs exactly.
        assert count_after_second == total_pairs

    def test_fk_integrity_rejects_nonexistent_snapshot(self, fk_chain: dict[str, Any]) -> None:
        """Direct INSERT with bogus market_snapshot_id is rejected by the FK.

        Smoke check that FK constraints are truly active in precog_test
        (migration drift could silently demote them). We bypass the
        writer and attempt a raw insert of a temporal_alignment row
        referencing an impossible snapshot id. psycopg2 surfaces the
        violation as IntegrityError on commit.
        """
        now = datetime.now(tz=UTC)
        bogus_ms_id = 2_000_000_000  # Safely outside any real sequence.

        with pytest.raises(psycopg2.errors.ForeignKeyViolation, match=r"market_snapshot_id"):
            with get_cursor(commit=True) as cur:
                # Need a real game_state to isolate the failure to the
                # market_snapshot FK (not a cascade of other FK errors).
                gs_id = _insert_game_state(
                    cur,
                    espn_event_id=fk_chain["espn_event_id"],
                    league_id=fk_chain["league_id"],
                    game_id=fk_chain["game_id"],
                    row_start_ts=now - timedelta(seconds=10),
                )
                cur.execute(
                    """
                    INSERT INTO temporal_alignment (
                        market_id, market_snapshot_id, game_state_id,
                        snapshot_time, game_state_time,
                        time_delta_seconds, alignment_quality, game_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        fk_chain["market_id"],
                        bogus_ms_id,
                        gs_id,
                        now,
                        now,
                        Decimal("0.5"),
                        "exact",
                        fk_chain["game_id"],
                    ),
                )
