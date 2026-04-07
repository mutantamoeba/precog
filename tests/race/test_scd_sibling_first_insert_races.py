"""
Race-condition tests for the 5 sibling SCD CRUD sites that adopted the
``retry_on_scd_unique_conflict`` helper from PR #631 / Issue #613.

Sites covered (one TestCase per site):
    - Issue #623: ``upsert_game_state`` in ``crud_game_states`` (first-insert
      race on ``idx_game_states_current_unique``).
    - Issue #624: ``upsert_game_odds`` in ``crud_game_states`` (first-insert
      race on ``uq_game_odds_game_book``). Note: the issue body prescribed
      ``uq_game_odds_game_sportsbook_current`` as the constraint, but
      migration 0048 creates two partial unique indexes on ``game_odds`` and
      PostgreSQL evaluates them in catalog (creation) order.
      ``uq_game_odds_game_book`` was created first, so it fires under the
      race -- empirically confirmed by this test's caplog assertions. See
      the inline rationale comment in ``upsert_game_odds`` for full
      explanation, and ``memory/feedback_issue_body_identifier_decay.md``
      for the broader lesson.
    - Issue #625: ``update_market_with_versioning`` in ``crud_markets``
      (concurrent-update race on ``idx_market_snapshots_unique_current``).
    - Issue #626: ``update_position_price`` in ``crud_positions``
      (concurrent-update race on ``idx_positions_unique_current``).
    - Issue #627: ``close_position`` in ``crud_positions`` (concurrent-close
      race on ``idx_positions_unique_current``).
    - Issue #628 / #629: ``set_trailing_stop_state`` in ``crud_positions``
      (concurrent-update race on ``idx_positions_unique_current``). The
      underlying #629 bug was a same-transaction READ COMMITTED visibility
      issue (UPDATE then INSERT...SELECT in one transaction); this race
      test guards the new CRUD function the same way the #626 race test
      guards ``update_position_price``.

These tests use TWO real database connections (via ``ThreadPoolExecutor``)
and a ``threading.Barrier`` to maximize the probability of an actual race.
Each test asserts that:
    1. Both threads return a valid id (neither raises).
    2. Exactly one row has ``row_current_ind = TRUE`` afterwards.
    3. The retry path fired at least once across the iteration loop
       (caplog-based assertion on the retry helper's WARNING message).

The race-exerciser test pattern is identical to
``tests/race/test_account_balance_concurrent_first_insert.py``. Per-iteration
state reset makes every loop a genuine race scenario; the caplog WARNING
assertion catches scheduler-serialized green runs that otherwise give false
coverage.

Reference:
    - Parent: Issue #613, PR #631 (helper + canonical adopter)
    - TESTING_STRATEGY V3.9 - Race tests for concurrent safety
    - Pattern 49 (DEVELOPMENT_PATTERNS_V1.30.md)

Skip Policy: Database race tests skip in CI by convention (matches
``tests/fixtures/stress_testcontainers.py:_is_ci``). Local-developer and
nightly testcontainer paths provide full coverage.

Usage:
    pytest tests/race/test_scd_sibling_first_insert_races.py -v -m race
"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from precog.database.connection import get_cursor
from precog.database.crud_game_states import (
    upsert_game_odds,
    upsert_game_state,
)
from precog.database.crud_markets import update_market_with_versioning
from precog.database.crud_positions import (
    close_position,
    set_trailing_stop_state,
    update_position_price,
)

# CI detection mirrors tests/fixtures/stress_testcontainers.py:_is_ci.
_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"

# Shared retry WARNING message fragment the helper emits through the caller's
# logger_override. Tests assert this appears at least once per loop.
_RETRY_WARNING_FRAGMENT = "SCD partial-unique-index conflict"

_NUM_ITERATIONS = 30

# Reserved test identifiers. The race teardowns explicitly delete these.
_TEST_ESPN_EVENT_ID = "TEST-RACE-623-EVENT"
_TEST_GAME_ODDS_SPORT = "football"
_TEST_GAME_ODDS_SPORTSBOOK = "test_race_draftkings_624"
_TEST_MARKET_TICKER = "TEST-RACE-625-MKT"
_TEST_MARKET_EXTERNAL_ID = "TEST-RACE-625-EXT"
_TEST_POSITION_BK_PREFIX = "TEST-RACE-POS-"


# =============================================================================
# Shared skip decorator
# =============================================================================


_skip_in_ci = pytest.mark.skipif(
    _is_ci,
    reason=(
        "DB race tests skip in CI by convention (matches "
        "tests/fixtures/stress_testcontainers.py:_is_ci). Local-developer "
        "and nightly testcontainer paths cover these tests."
    ),
)


# =============================================================================
# Helper: barrier-synchronized two-thread race runner
# =============================================================================


def _run_two_thread_race(
    fn_a: Any,
    fn_b: Any,
) -> tuple[dict[str, Any], dict[str, Exception | None]]:
    """Run ``fn_a`` and ``fn_b`` concurrently behind a barrier.

    Each fn is a zero-arg callable; the return value is captured in
    ``results[label]``. Any exception is captured in ``errors[label]`` so
    the caller can make structured assertions without letting the helper
    swallow failures.
    """
    barrier = threading.Barrier(parties=2)
    results: dict[str, Any] = {"a": None, "b": None}
    errors: dict[str, Exception | None] = {"a": None, "b": None}

    def _attempt(label: str, fn: Any) -> None:
        try:
            barrier.wait(timeout=10.0)
            results[label] = fn()
        except Exception as exc:  # pragma: no cover - failure path
            errors[label] = exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(_attempt, "a", fn_a),
            executor.submit(_attempt, "b", fn_b),
        ]
        for future in as_completed(futures):
            future.result()

    return results, errors


# =============================================================================
# Issue #623 — upsert_game_state first-insert race
# =============================================================================


@pytest.fixture
def game_state_race_setup(db_pool: Any) -> Any:
    """Ensure clean game_states state for the test espn_event_id."""
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM game_states WHERE espn_event_id = %s",
            (_TEST_ESPN_EVENT_ID,),
        )
    yield _TEST_ESPN_EVENT_ID
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM game_states WHERE espn_event_id = %s",
                (_TEST_ESPN_EVENT_ID,),
            )
    except Exception:
        pass


@pytest.mark.race
@_skip_in_ci
class TestUpsertGameStateConcurrentFirstInsert:
    """Issue #623: two-thread first-insert race on game_states."""

    def test_concurrent_first_insert_resolved_by_retry(
        self,
        game_state_race_setup: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        espn_event_id = game_state_race_setup

        with caplog.at_level(logging.WARNING):
            for iteration in range(_NUM_ITERATIONS):
                # Clean slate each iteration so every pass is a genuine
                # first-insert.
                with get_cursor(commit=True) as cur:
                    cur.execute(
                        "DELETE FROM game_states WHERE espn_event_id = %s",
                        (espn_event_id,),
                    )

                def call_a(_eid: str = espn_event_id) -> int | None:
                    return upsert_game_state(
                        espn_event_id=_eid,
                        home_score=7,
                        away_score=3,
                        period=1,
                        game_status="in_progress",
                        league="nfl",
                        skip_if_unchanged=False,
                    )

                def call_b(_eid: str = espn_event_id) -> int | None:
                    return upsert_game_state(
                        espn_event_id=_eid,
                        home_score=14,
                        away_score=10,
                        period=2,
                        game_status="in_progress",
                        league="nfl",
                        skip_if_unchanged=False,
                    )

                results, errors = _run_two_thread_race(call_a, call_b)

                assert errors["a"] is None, (
                    f"iteration {iteration}: thread A raised: {errors['a']!r}"
                )
                assert errors["b"] is None, (
                    f"iteration {iteration}: thread B raised: {errors['b']!r}"
                )
                assert results["a"] is not None
                assert results["b"] is not None

                # Verify exactly one current row, and the chain has at most
                # two rows (one historical if the retry fired, or one
                # current if the race serialized cleanly).
                with get_cursor(commit=False) as cur:
                    cur.execute(
                        """
                        SELECT id, row_current_ind
                        FROM game_states
                        WHERE espn_event_id = %s
                        """,
                        (espn_event_id,),
                    )
                    rows = cur.fetchall()

                current_rows = [r for r in rows if r["row_current_ind"]]
                assert len(current_rows) == 1, (
                    f"iteration {iteration}: expected exactly one current "
                    f"row, found {len(current_rows)}"
                )

        retry_warnings = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING and _RETRY_WARNING_FRAGMENT in r.getMessage()
        ]
        assert len(retry_warnings) >= 1, (
            f"upsert_game_state race test ran {_NUM_ITERATIONS} iterations "
            f"without firing the retry path. The threads are serializing "
            f"and the test is providing false coverage."
        )


# =============================================================================
# Issue #624 — upsert_game_odds first-insert race
# =============================================================================


@pytest.fixture
def game_odds_race_setup(db_pool: Any) -> Any:
    """Create a test game row and return its id; clean up game_odds rows."""
    test_sportsbook = _TEST_GAME_ODDS_SPORTSBOOK
    test_home_code = "RACE_HOME"
    test_away_code = "RACE_AWAY"
    test_game_date = date(2026, 9, 15)

    with get_cursor(commit=True) as cur:
        # Remove any prior test game + game_odds rows.
        cur.execute(
            """
            DELETE FROM game_odds
            WHERE game_id IN (
                SELECT id FROM games
                WHERE sport = %s AND home_team_code = %s AND away_team_code = %s
                  AND game_date = %s
            )
            """,
            (_TEST_GAME_ODDS_SPORT, test_home_code, test_away_code, test_game_date),
        )
        cur.execute(
            """
            DELETE FROM games
            WHERE sport = %s AND home_team_code = %s AND away_team_code = %s
              AND game_date = %s
            """,
            (_TEST_GAME_ODDS_SPORT, test_home_code, test_away_code, test_game_date),
        )

        # Create a fresh game row. Natural key is
        # (sport, game_date, home_team_code, away_team_code).
        cur.execute(
            """
            INSERT INTO games (
                sport, game_date, home_team_code, away_team_code,
                season, league, game_status, data_source
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                _TEST_GAME_ODDS_SPORT,
                test_game_date,
                test_home_code,
                test_away_code,
                2026,
                "nfl",
                "scheduled",
                "espn",
            ),
        )
        row = cur.fetchone()
        game_id = row["id"]

    yield game_id, test_sportsbook, test_home_code, test_away_code, test_game_date

    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM game_odds WHERE game_id = %s", (game_id,))
            cur.execute("DELETE FROM games WHERE id = %s", (game_id,))
    except Exception:
        pass


@pytest.mark.race
@_skip_in_ci
class TestUpsertGameOddsConcurrentFirstInsert:
    """Issue #624: two-thread first-insert race on game_odds."""

    def test_concurrent_first_insert_resolved_by_retry(
        self,
        game_odds_race_setup: Any,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        game_id, sportsbook, home_code, away_code, game_date = game_odds_race_setup

        with caplog.at_level(logging.WARNING):
            for iteration in range(_NUM_ITERATIONS):
                with get_cursor(commit=True) as cur:
                    cur.execute(
                        "DELETE FROM game_odds WHERE game_id = %s AND sportsbook = %s",
                        (game_id, sportsbook),
                    )

                def call_a(
                    _gid: int = game_id,
                    _sb: str = sportsbook,
                    _hc: str = home_code,
                    _ac: str = away_code,
                    _gd: date = game_date,
                ) -> int | None:
                    return upsert_game_odds(
                        game_id=_gid,
                        sport=_TEST_GAME_ODDS_SPORT,
                        sportsbook=_sb,
                        game_date=_gd,
                        home_team_code=_hc,
                        away_team_code=_ac,
                        spread_home_close=Decimal("3.5"),
                        moneyline_home_close=-150,
                        moneyline_away_close=130,
                        total_close=Decimal("47.5"),
                    )

                def call_b(
                    _gid: int = game_id,
                    _sb: str = sportsbook,
                    _hc: str = home_code,
                    _ac: str = away_code,
                    _gd: date = game_date,
                ) -> int | None:
                    return upsert_game_odds(
                        game_id=_gid,
                        sport=_TEST_GAME_ODDS_SPORT,
                        sportsbook=_sb,
                        game_date=_gd,
                        home_team_code=_hc,
                        away_team_code=_ac,
                        spread_home_close=Decimal("4.0"),
                        moneyline_home_close=-160,
                        moneyline_away_close=140,
                        total_close=Decimal("48.0"),
                    )

                results, errors = _run_two_thread_race(call_a, call_b)

                assert errors["a"] is None
                assert errors["b"] is None
                assert results["a"] is not None
                assert results["b"] is not None

                with get_cursor(commit=False) as cur:
                    cur.execute(
                        """
                        SELECT id, row_current_ind
                        FROM game_odds
                        WHERE game_id = %s AND sportsbook = %s
                        """,
                        (game_id, sportsbook),
                    )
                    rows = cur.fetchall()

                current_rows = [r for r in rows if r["row_current_ind"]]
                assert len(current_rows) == 1

        retry_warnings = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING and _RETRY_WARNING_FRAGMENT in r.getMessage()
        ]
        assert len(retry_warnings) >= 1, (
            f"upsert_game_odds race test ran {_NUM_ITERATIONS} iterations "
            f"without firing the retry path."
        )


# =============================================================================
# Issue #625 — update_market_with_versioning concurrent-update race
# =============================================================================


@pytest.fixture
def market_race_setup(db_pool: Any) -> Any:
    """Create a test market with an initial snapshot and clean up after."""
    with get_cursor(commit=True) as cur:
        # Remove any prior test market + snapshots.
        cur.execute(
            """
            DELETE FROM market_snapshots
            WHERE market_id IN (SELECT id FROM markets WHERE ticker = %s)
            """,
            (_TEST_MARKET_TICKER,),
        )
        cur.execute("DELETE FROM markets WHERE ticker = %s", (_TEST_MARKET_TICKER,))

        # Insert the dimension row.
        cur.execute(
            """
            INSERT INTO markets (
                platform_id, event_internal_id, external_id, ticker, title,
                market_type, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                "kalshi",
                None,
                _TEST_MARKET_EXTERNAL_ID,
                _TEST_MARKET_TICKER,
                "Race Test Market 625",
                "binary",
                "open",
            ),
        )
        market_pk = cur.fetchone()["id"]

        # Insert the initial current snapshot. The concurrent-update race
        # needs an existing current row so both callers pass get_current_market.
        cur.execute(
            """
            INSERT INTO market_snapshots (
                market_id, yes_ask_price, no_ask_price,
                row_current_ind, row_start_ts, updated_at
            )
            VALUES (%s, %s, %s, TRUE, NOW(), NOW())
            """,
            (market_pk, Decimal("0.5000"), Decimal("0.5000")),
        )

    yield _TEST_MARKET_TICKER, market_pk

    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM market_snapshots WHERE market_id = %s", (market_pk,))
            cur.execute("DELETE FROM markets WHERE id = %s", (market_pk,))
    except Exception:
        pass


@pytest.mark.race
@_skip_in_ci
class TestUpdateMarketConcurrentUpdateRace:
    """Issue #625: two-thread concurrent-update race on market_snapshots."""

    def test_concurrent_update_resolved_by_retry(
        self,
        market_race_setup: Any,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        ticker, market_pk = market_race_setup

        with caplog.at_level(logging.WARNING):
            for iteration in range(_NUM_ITERATIONS):
                # Reset state: one current snapshot, no history.
                with get_cursor(commit=True) as cur:
                    cur.execute(
                        "DELETE FROM market_snapshots WHERE market_id = %s",
                        (market_pk,),
                    )
                    cur.execute(
                        """
                        INSERT INTO market_snapshots (
                            market_id, yes_ask_price, no_ask_price,
                            row_current_ind, row_start_ts, updated_at
                        )
                        VALUES (%s, %s, %s, TRUE, NOW(), NOW())
                        """,
                        (market_pk, Decimal("0.5000"), Decimal("0.5000")),
                    )

                def call_a(_t: str = ticker) -> int:
                    return update_market_with_versioning(
                        ticker=_t,
                        yes_ask_price=Decimal("0.5500"),
                        no_ask_price=Decimal("0.4500"),
                    )

                def call_b(_t: str = ticker) -> int:
                    return update_market_with_versioning(
                        ticker=_t,
                        yes_ask_price=Decimal("0.6000"),
                        no_ask_price=Decimal("0.4000"),
                    )

                results, errors = _run_two_thread_race(call_a, call_b)

                assert errors["a"] is None, (
                    f"iteration {iteration}: thread A raised: {errors['a']!r}"
                )
                assert errors["b"] is None, (
                    f"iteration {iteration}: thread B raised: {errors['b']!r}"
                )

                # Both calls should return the same market_pk.
                assert results["a"] == market_pk
                assert results["b"] == market_pk

                # Exactly one current snapshot row afterward.
                with get_cursor(commit=False) as cur:
                    cur.execute(
                        """
                        SELECT id, row_current_ind
                        FROM market_snapshots
                        WHERE market_id = %s
                        """,
                        (market_pk,),
                    )
                    rows = cur.fetchall()

                current_rows = [r for r in rows if r["row_current_ind"]]
                assert len(current_rows) == 1

        # NOTE: Issue #625 is a concurrent-UPDATE race, not a first-insert
        # race. The primary fix is the FOR UPDATE lock inside the closure,
        # which serializes concurrent callers against an EXISTING current
        # row. The retry helper is defensive belt-and-suspenders against
        # exotic scenarios (e.g., current row vanishes between lock and
        # insert). Because FOR UPDATE normally resolves the race cleanly,
        # the retry path does NOT need to fire — and asserting that it
        # must would turn healthy serialization into a test failure. The
        # test's primary invariant is "no exceptions, exactly one current
        # row per iteration", not "retry path fired".


# =============================================================================
# Issue #626 — update_position_price concurrent-update race
# =============================================================================
# Issue #627 — close_position concurrent-close race
# =============================================================================


@pytest.fixture
def position_race_setup(db_pool: Any) -> Any:
    """Create a test market + position for the positions race tests."""
    test_ticker = f"{_TEST_MARKET_TICKER}-POS"
    position_bk = f"{_TEST_POSITION_BK_PREFIX}{int(datetime.now(UTC).timestamp())}"

    with get_cursor(commit=True) as cur:
        # Clean up any prior test data.
        cur.execute(
            "DELETE FROM positions WHERE position_id LIKE %s",
            (_TEST_POSITION_BK_PREFIX + "%",),
        )
        cur.execute(
            """
            DELETE FROM market_snapshots WHERE market_id IN (
                SELECT id FROM markets WHERE ticker = %s
            )
            """,
            (test_ticker,),
        )
        cur.execute("DELETE FROM markets WHERE ticker = %s", (test_ticker,))

        # Create the underlying market (positions FK to markets.id).
        cur.execute(
            """
            INSERT INTO markets (
                platform_id, event_internal_id, external_id, ticker, title,
                market_type, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                "kalshi",
                None,
                f"{test_ticker}-EXT",
                test_ticker,
                "Race Test Market Positions",
                "binary",
                "open",
            ),
        )
        market_pk = cur.fetchone()["id"]

        # Create the initial current position row.
        # execution_environment is explicit (not relying on the DB default)
        # per the #622+#686 synthesis principle: every code path should be
        # explicit about which environment it writes, even when using raw
        # SQL. Seeded as 'paper' so future race tests can verify the column
        # is preserved across concurrent operations.
        cur.execute(
            """
            INSERT INTO positions (
                position_id, market_internal_id, side, quantity,
                entry_price, current_price,
                status, entry_time, last_check_time,
                row_current_ind, row_start_ts,
                execution_environment
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), TRUE, NOW(), %s)
            RETURNING id
            """,
            (
                position_bk,
                market_pk,
                "YES",
                10,
                Decimal("0.5000"),
                Decimal("0.5000"),
                "open",
                "paper",
            ),
        )
        position_surrogate_id = cur.fetchone()["id"]

    yield position_bk, market_pk, position_surrogate_id

    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM positions WHERE position_id = %s", (position_bk,))
            cur.execute("DELETE FROM market_snapshots WHERE market_id = %s", (market_pk,))
            cur.execute("DELETE FROM markets WHERE id = %s", (market_pk,))
    except Exception:
        pass


def _reset_position(position_bk: str, market_pk: int) -> int:
    """Reset the positions chain to a single current row; return its id.

    execution_environment is explicit ('paper') per the #622+#686 synthesis
    principle. Matches the seeding in position_race_setup.
    """
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM positions WHERE position_id = %s", (position_bk,))
        cur.execute(
            """
            INSERT INTO positions (
                position_id, market_internal_id, side, quantity,
                entry_price, current_price,
                status, entry_time, last_check_time,
                row_current_ind, row_start_ts,
                execution_environment
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), TRUE, NOW(), %s)
            RETURNING id
            """,
            (
                position_bk,
                market_pk,
                "YES",
                10,
                Decimal("0.5000"),
                Decimal("0.5000"),
                "open",
                "paper",
            ),
        )
        return int(cur.fetchone()["id"])


@pytest.mark.race
@_skip_in_ci
class TestUpdatePositionPriceConcurrentUpdate:
    """Issue #626: two-thread concurrent-update race on positions."""

    def test_concurrent_price_update_resolved_by_retry(
        self,
        position_race_setup: Any,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        position_bk, market_pk, _initial_surrogate_id = position_race_setup

        with caplog.at_level(logging.WARNING):
            for iteration in range(_NUM_ITERATIONS):
                fresh_surrogate = _reset_position(position_bk, market_pk)

                def call_a(_sid: int = fresh_surrogate) -> int:
                    return update_position_price(
                        position_id=_sid,
                        current_price=Decimal("0.5500"),
                    )

                def call_b(_sid: int = fresh_surrogate) -> int:
                    return update_position_price(
                        position_id=_sid,
                        current_price=Decimal("0.6000"),
                    )

                results, errors = _run_two_thread_race(call_a, call_b)

                assert errors["a"] is None, (
                    f"iteration {iteration}: thread A raised: {errors['a']!r}"
                )
                assert errors["b"] is None, (
                    f"iteration {iteration}: thread B raised: {errors['b']!r}"
                )
                assert results["a"] is not None
                assert results["b"] is not None

                with get_cursor(commit=False) as cur:
                    cur.execute(
                        """
                        SELECT id, row_current_ind
                        FROM positions
                        WHERE position_id = %s
                        """,
                        (position_bk,),
                    )
                    rows = cur.fetchall()

                current_rows = [r for r in rows if r["row_current_ind"]]
                assert len(current_rows) == 1

        # NOTE: Issue #626 is a concurrent-UPDATE race, not a first-insert
        # race. FOR UPDATE serializes the two callers against the existing
        # current row. The retry helper is defensive. See the equivalent
        # comment in TestUpdateMarketConcurrentUpdateRace above.


@pytest.mark.race
@_skip_in_ci
class TestClosePositionConcurrentClose:
    """Issue #627: two-thread concurrent-close race on positions."""

    def test_concurrent_close_resolved_by_retry(
        self,
        position_race_setup: Any,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        position_bk, market_pk, _initial_surrogate_id = position_race_setup

        with caplog.at_level(logging.WARNING):
            for iteration in range(_NUM_ITERATIONS):
                fresh_surrogate = _reset_position(position_bk, market_pk)

                def call_a(_sid: int = fresh_surrogate) -> int:
                    return close_position(
                        position_id=_sid,
                        exit_price=Decimal("0.6000"),
                        exit_reason="target_hit",
                        realized_pnl=Decimal("1.0000"),
                    )

                def call_b(_sid: int = fresh_surrogate) -> int:
                    return close_position(
                        position_id=_sid,
                        exit_price=Decimal("0.4000"),
                        exit_reason="stop_loss",
                        realized_pnl=Decimal("-1.0000"),
                    )

                results, errors = _run_two_thread_race(call_a, call_b)

                # Brawne CONCERN 1 (#627 diff-scoped review): under
                # concurrent close, the SECOND caller's retry attempt
                # re-fetches the current row, observes status='closed'
                # from the FIRST caller's commit, and refuses to overwrite
                # by raising ValueError. This replaces the OLD behavior
                # where both callers could succeed and the second's
                # exit_price/realized_pnl silently clobbered the first.
                # The race test now asserts EXACTLY ONE thread wins and
                # EXACTLY ONE raises ValueError with the "already closed"
                # message -- which is the loud failure mode that
                # position_manager.close_position's `except ValueError`
                # handler is designed to surface to the caller.
                a_raised = errors["a"] is not None
                b_raised = errors["b"] is not None
                assert a_raised != b_raised, (
                    f"iteration {iteration}: expected exactly one thread "
                    f"to raise (the loser of the close race), but got "
                    f"a_raised={a_raised}, b_raised={b_raised}. "
                    f"errors={errors!r}"
                )
                loser_exc = errors["a"] if a_raised else errors["b"]
                assert isinstance(loser_exc, ValueError), (
                    f"iteration {iteration}: loser raised "
                    f"{type(loser_exc).__name__}, expected ValueError"
                )
                assert "is not open" in str(loser_exc), (
                    f"iteration {iteration}: loser ValueError message "
                    f"did not match the expected 'is not open' guard "
                    f"(hardened from 'is already closed' per Marvin): "
                    f"{loser_exc!r}"
                )
                winner_id = results["a"] if not a_raised else results["b"]
                assert winner_id is not None

                with get_cursor(commit=False) as cur:
                    cur.execute(
                        """
                        SELECT id, row_current_ind, status
                        FROM positions
                        WHERE position_id = %s
                        """,
                        (position_bk,),
                    )
                    rows = cur.fetchall()

                current_rows = [r for r in rows if r["row_current_ind"]]
                assert len(current_rows) == 1, (
                    f"iteration {iteration}: expected exactly one current "
                    f"position row, found {len(current_rows)}"
                )
                # The current row should be the WINNER's close (status='closed').
                assert current_rows[0]["status"] == "closed"
                assert current_rows[0]["id"] == winner_id, (
                    f"iteration {iteration}: current row id "
                    f"{current_rows[0]['id']} does not match the winning "
                    f"thread's returned id {winner_id}. The winner's close "
                    f"should be the surviving current row."
                )

        # NOTE: Issue #627 is a concurrent-CLOSE race. Unlike #623/#624
        # (first-insert races where the helper makes both callers succeed)
        # and #625/#626 (concurrent-update races where FOR UPDATE serializes
        # both callers and both succeed), close races MUST surface the loser
        # loudly because the second close's exit_price/realized_pnl would
        # silently clobber the first close's. The status-check guard inside
        # the closure (added per Brawne CONCERN 1) is the loudness mechanism.


# =============================================================================
# Issue #628 / #629 — set_trailing_stop_state concurrent-update race
# =============================================================================


@pytest.mark.race
@_skip_in_ci
class TestSetTrailingStopStateConcurrentUpdate:
    """Issue #628 / #629: two-thread concurrent-update race on
    ``set_trailing_stop_state``.

    The underlying #629 bug was a same-transaction READ COMMITTED visibility
    issue: ``UPDATE positions SET row_current_ind = FALSE`` followed by
    ``INSERT ... SELECT FROM positions WHERE row_current_ind = TRUE`` in
    one transaction returned zero rows from the SELECT and silently
    inserted nothing. PR #629 extracted ``set_trailing_stop_state`` in
    ``crud_positions``, mirroring the canonical Pattern 49 shape from
    ``update_position_price`` (PR #665), which captures all column values
    into Python BEFORE the close and INSERTs from those captured values.

    This race test asserts the same invariants as #626's
    ``update_position_price`` race: under two concurrent callers racing
    on the same business key, both callers return a valid id, exactly one
    row remains current, and the SCD chain stays consistent. FOR UPDATE
    serializes the close+insert sequence so the retry helper does not
    typically need to fire (the test does not assert on caplog WARNINGs
    for that reason -- mirroring ``TestUpdatePositionPriceConcurrentUpdate``).
    """

    def test_concurrent_trailing_stop_update_resolved_by_retry(
        self,
        position_race_setup: Any,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        position_bk, market_pk, _initial_surrogate_id = position_race_setup

        # Two distinct trailing stop states so we can verify the SCD row
        # surviving as current is one of the two payloads (not a hybrid).
        state_a = {
            "config": {
                "activation_threshold": "0.15",
                "initial_distance": "0.05",
                "tightening_rate": "0.10",
                "floor_distance": "0.02",
            },
            "activated": False,
            "activation_price": None,
            "current_stop_price": "0.4500",
            "highest_price": "0.5500",
            "_marker": "thread_a",
        }
        state_b = {
            "config": state_a["config"],
            "activated": True,
            "activation_price": "0.6500",
            "current_stop_price": "0.6000",
            "highest_price": "0.6500",
            "_marker": "thread_b",
        }

        with caplog.at_level(logging.WARNING):
            for iteration in range(_NUM_ITERATIONS):
                fresh_surrogate = _reset_position(position_bk, market_pk)

                def call_a(_sid: int = fresh_surrogate) -> int:
                    return set_trailing_stop_state(
                        position_id=_sid,
                        trailing_stop_state=state_a,
                        current_price=Decimal("0.5500"),
                        unrealized_pnl=Decimal("0.5000"),
                    )

                def call_b(_sid: int = fresh_surrogate) -> int:
                    return set_trailing_stop_state(
                        position_id=_sid,
                        trailing_stop_state=state_b,
                        current_price=Decimal("0.6500"),
                        unrealized_pnl=Decimal("1.5000"),
                    )

                results, errors = _run_two_thread_race(call_a, call_b)

                assert errors["a"] is None, (
                    f"iteration {iteration}: thread A raised: {errors['a']!r}"
                )
                assert errors["b"] is None, (
                    f"iteration {iteration}: thread B raised: {errors['b']!r}"
                )
                assert results["a"] is not None
                assert results["b"] is not None

                with get_cursor(commit=False) as cur:
                    cur.execute(
                        """
                        SELECT id, row_current_ind, trailing_stop_state,
                               execution_environment
                        FROM positions
                        WHERE position_id = %s
                        """,
                        (position_bk,),
                    )
                    rows = cur.fetchall()

                current_rows = [r for r in rows if r["row_current_ind"]]
                assert len(current_rows) == 1, (
                    f"iteration {iteration}: expected exactly one current "
                    f"position row, found {len(current_rows)}"
                )

                # The surviving current row's trailing_stop_state must be
                # ONE of the two payloads -- never a hybrid. The marker
                # field discriminates which thread won.
                surviving_marker = current_rows[0]["trailing_stop_state"].get("_marker")
                assert surviving_marker in {"thread_a", "thread_b"}, (
                    f"iteration {iteration}: surviving trailing_stop_state "
                    f"is neither thread A nor thread B's payload (no _marker "
                    f"or unknown _marker={surviving_marker!r}). The CRUD "
                    f"function may have produced a hybrid write."
                )

                # execution_environment must be preserved for EVERY row in
                # the chain (not silently defaulted to 'live'). The
                # _reset_position fixture seeds the chain with the default
                # 'live' value, but we still verify the assertion holds in
                # case a future fixture switches to 'paper'.
                envs = {r["execution_environment"] for r in rows}
                assert len(envs) == 1, (
                    f"iteration {iteration}: execution_environment varies "
                    f"across the SCD chain: {envs}. The CRUD function "
                    f"failed to preserve the column on at least one row."
                )

        # NOTE: Issues #628/#629 are concurrent-UPDATE races (not first-insert
        # races). FOR UPDATE serializes the two callers against the existing
        # current row in the typical case, so the retry helper does NOT need
        # to fire on every iteration -- asserting that it must would turn
        # healthy serialization into a test failure. The primary invariants
        # are "no exceptions, exactly one current row, surviving payload is
        # one of the two threads' (not a hybrid), and execution_environment
        # is preserved across the chain." See the equivalent NOTE on
        # ``TestUpdatePositionPriceConcurrentUpdate`` (#626).
