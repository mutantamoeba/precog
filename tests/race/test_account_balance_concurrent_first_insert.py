"""
Race-condition tests for the SCD first-insert race in
``update_account_balance_with_versioning``.

Issue #613: Migration 0049 added the partial unique index
``idx_balance_unique_current`` on ``account_balance(platform_id) WHERE
row_current_ind = TRUE``. The CRUD function uses ``FOR UPDATE`` to serialize
concurrent updates, but on the FIRST insert for a platform there is no row to
lock -- two callers can both proceed past the lock query and collide on the
partial unique index. The retry helper added in this issue catches that
specific collision and retries in a fresh transaction so the second caller
sees the sibling's now-committed row.

These tests use TWO real database connections (via ``ThreadPoolExecutor``)
and a ``threading.Barrier`` to maximize the probability of an actual race.
The tests assert that:
    1. Both threads return a valid balance_id (neither raises).
    2. Exactly one row has ``row_current_ind = TRUE`` afterwards.
    3. The version chain has exactly two rows total for the test platform.
    4. The current balance matches one of the two threads' inputs.

Reference: TESTING_STRATEGY V3.9 - Race tests for concurrent safety.
Skip Policy: Database race tests require Docker/testcontainers locally and
the CI PostgreSQL service container; in CI we use the standard ``db_pool``
fixture from ``tests/conftest.py``. Where the test cannot be run (e.g.,
hostile CI without DB), the ``_is_ci`` skip is applied to keep test runs
green; the local-developer / nightly path provides full coverage.

Usage:
    pytest tests/race/test_account_balance_concurrent_first_insert.py -v -m race
"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from typing import Any

import pytest

from precog.database.connection import get_cursor
from precog.database.crud_account import update_account_balance_with_versioning

# CI detection mirrors tests/fixtures/stress_testcontainers.py:_is_ci so the
# convention is consistent across the test suite.
_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"

# Test platform identifier reserved for this race test. The clean_test_data
# fixture deletes platforms with `test_%` and `TEST-PLATFORM-%` prefixes, so
# this prefix keeps cleanup compatible with the suite-wide fixture.
_TEST_PLATFORM_ID = "test_race_613"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def race_platform(db_pool: Any) -> Any:
    """Create a clean test platform for the race test and tear it down after.

    The fixture explicitly clears any prior account_balance rows for the test
    platform AND any cascading FKs (settlements). It uses its own
    ``get_cursor(commit=True)`` blocks rather than the suite-wide
    ``clean_test_data`` rollback fixture, because the race threads commit
    real rows that survive a SAVEPOINT-style rollback.
    """
    # Setup: ensure clean state and the platform row exists.
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM settlements WHERE platform_id = %s",
            (_TEST_PLATFORM_ID,),
        )
        cur.execute(
            "DELETE FROM account_balance WHERE platform_id = %s",
            (_TEST_PLATFORM_ID,),
        )
        cur.execute(
            """
            INSERT INTO platforms (platform_id, platform_type, display_name, base_url, status)
            VALUES (%s, 'trading', 'Race Test Platform 613', 'https://race-613.test', 'active')
            ON CONFLICT (platform_id) DO NOTHING
            """,
            (_TEST_PLATFORM_ID,),
        )

    yield _TEST_PLATFORM_ID

    # Teardown: remove all rows we created.
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM settlements WHERE platform_id = %s",
                (_TEST_PLATFORM_ID,),
            )
            cur.execute(
                "DELETE FROM account_balance WHERE platform_id = %s",
                (_TEST_PLATFORM_ID,),
            )
            cur.execute(
                "DELETE FROM platforms WHERE platform_id = %s",
                (_TEST_PLATFORM_ID,),
            )
    except Exception:
        # Best-effort cleanup; do not fail the test on teardown problems.
        pass


# =============================================================================
# Race tests
# =============================================================================


@pytest.mark.race
@pytest.mark.skipif(
    _is_ci,
    reason=(
        "DB race tests skip in CI by convention (matches "
        "tests/fixtures/stress_testcontainers.py:_is_ci). The local-developer "
        "and nightly testcontainer paths cover this test."
    ),
)
class TestAccountBalanceConcurrentFirstInsert:
    """Two-thread first-insert race against the partial unique index."""

    def test_concurrent_first_insert_resolved_by_retry(
        self, race_platform: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Two callers race the FIRST insert; helper retry must resolve cleanly.

        Holden Condition 7 (issue #613): both calls must succeed (the retry
        helper catches the second caller's UniqueViolation and retries in a
        fresh transaction), exactly one current row must remain, and the
        version chain must contain exactly two rows total -- one historical
        (the loser of the race, immediately closed by the winner's retry)
        and one current.

        FIX 8 (Marvin Scenario 7): we run the two-thread race 50 iterations
        with per-iteration state reset. Running the race once let OS
        scheduling serialize the threads often enough that the retry path
        never fired, giving false green coverage. The loop plus the
        caplog-based assertion on the WARNING log turns "retry path fired at
        least once" into a hard invariant of the test.

        FIX 9 (Marvin Scenario 23): per-iteration temporal-continuity check
        (historical.row_end_ts == current.row_start_ts) to guard Pattern 49.

        FIX 10 (Marvin Scenario 24): per-iteration thread-balance attribution
        -- the current row's balance must match the thread whose returned
        balance_id is the current row's id.
        """
        # Two distinct balances so we can identify which thread "won" (became
        # the current row) versus which thread's row was retried into a
        # close+insert sequence.
        balance_thread_a = Decimal("1000.0000")
        balance_thread_b = Decimal("2500.0000")

        num_iterations = 50

        # PR #631 / Claude Review Issue 4: capture WARNINGs from ALL loggers,
        # not just precog.database.crud_account. The retry helper currently
        # logs through ``logger_override=logger`` (the crud_account module
        # logger), but if a future caller passes ``logger_override=None`` or
        # routes through a different logger, a logger-restricted caplog would
        # miss the retry WARNING and the ``len(retry_warnings) >= 1`` assertion
        # below would give a false green. The message-content filter
        # (``"SCD partial-unique-index conflict" in r.getMessage()``) is
        # sufficient to discriminate retry warnings from any unrelated
        # warnings emitted during the test.
        with caplog.at_level(logging.WARNING):
            for iteration in range(num_iterations):
                # Clean state at the start of each iteration so every pass is
                # a genuine "first insert" scenario.
                with get_cursor(commit=True) as cur:
                    cur.execute(
                        "DELETE FROM account_balance WHERE platform_id = %s",
                        (race_platform,),
                    )

                # Barrier ensures both threads call into the CRUD function at
                # the same instant, maximizing the chance the lock query in
                # each thread observes zero current rows simultaneously --
                # the precondition for the first-insert race.
                barrier = threading.Barrier(parties=2)

                results: dict[str, int | None] = {"a": None, "b": None}
                errors: dict[str, Exception | None] = {"a": None, "b": None}

                # Bind per-iteration state via default args so the closure
                # does not capture loop variables (B023). Each ThreadPool
                # submission gets a stable snapshot of barrier/results/errors.
                def attempt(
                    label: str,
                    balance: Decimal,
                    _barrier: threading.Barrier = barrier,
                    _results: dict[str, int | None] = results,
                    _errors: dict[str, Exception | None] = errors,
                    _platform: str = race_platform,
                ) -> None:
                    try:
                        _barrier.wait(timeout=10.0)
                        balance_id = update_account_balance_with_versioning(
                            platform_id=_platform,
                            new_balance=balance,
                            currency="USD",
                        )
                        _results[label] = balance_id
                    except Exception as exc:  # pragma: no cover - failure path
                        _errors[label] = exc

                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [
                        executor.submit(attempt, "a", balance_thread_a),
                        executor.submit(attempt, "b", balance_thread_b),
                    ]
                    for future in as_completed(futures):
                        # Surface any unexpected exceptions immediately.
                        future.result()

                # Both threads must have succeeded -- neither should have raised.
                assert errors["a"] is None, (
                    f"iteration {iteration}: thread A raised: {errors['a']!r}"
                )
                assert errors["b"] is None, (
                    f"iteration {iteration}: thread B raised: {errors['b']!r}"
                )
                assert results["a"] is not None, (
                    f"iteration {iteration}: thread A returned None for balance_id"
                )
                assert results["b"] is not None, (
                    f"iteration {iteration}: thread B returned None for balance_id"
                )

                # Verify the database invariants: exactly one current row,
                # exactly two rows total, and the current balance matches
                # one of the inputs.
                with get_cursor(commit=False) as cur:
                    cur.execute(
                        """
                        SELECT id, balance, row_current_ind, row_start_ts, row_end_ts
                        FROM account_balance
                        WHERE platform_id = %s
                        ORDER BY row_start_ts ASC
                        """,
                        (race_platform,),
                    )
                    rows = cur.fetchall()

                assert len(rows) == 2, (
                    f"iteration {iteration}: expected exactly 2 version rows "
                    f"after the race, found {len(rows)}: {rows}"
                )

                current_rows = [r for r in rows if r["row_current_ind"]]
                historical_rows = [r for r in rows if not r["row_current_ind"]]

                assert len(current_rows) == 1, (
                    f"iteration {iteration}: expected exactly one "
                    f"row_current_ind=TRUE row, found {len(current_rows)}"
                )
                assert len(historical_rows) == 1, (
                    f"iteration {iteration}: expected exactly one historical "
                    f"row, found {len(historical_rows)}"
                )

                current_row = current_rows[0]
                historical_row = historical_rows[0]

                current_balance = current_row["balance"]
                assert current_balance in (balance_thread_a, balance_thread_b), (
                    f"iteration {iteration}: current balance {current_balance} "
                    f"matches neither input ({balance_thread_a}, {balance_thread_b})"
                )

                # The historical row's row_end_ts should be set (it was
                # closed); the current row's row_end_ts should be NULL.
                assert historical_row["row_end_ts"] is not None, (
                    f"iteration {iteration}: historical row must have row_end_ts populated"
                )
                assert current_row["row_end_ts"] is None, (
                    f"iteration {iteration}: current row must have row_end_ts NULL"
                )

                # FIX 9: Pattern 49 temporal continuity -- historical row's
                # row_end_ts must equal current row's row_start_ts, leaving
                # no gap and no backward interval in the version chain.
                assert historical_row["row_end_ts"] == current_row["row_start_ts"], (
                    f"iteration {iteration}: temporal continuity violation: "
                    f"historical.row_end_ts={historical_row['row_end_ts']} != "
                    f"current.row_start_ts={current_row['row_start_ts']}"
                )

                # Both returned balance_ids must reference rows in the table,
                # and they must be distinct (one current, one historical).
                all_ids = {r["id"] for r in rows}
                assert results["a"] in all_ids, (
                    f"iteration {iteration}: thread A's balance_id "
                    f"{results['a']} not present in version chain"
                )
                assert results["b"] in all_ids, (
                    f"iteration {iteration}: thread B's balance_id "
                    f"{results['b']} not present in version chain"
                )
                assert results["a"] != results["b"], (
                    f"iteration {iteration}: both threads returned the same balance_id"
                )

                # FIX 10: thread-balance attribution. Whichever thread's
                # returned balance_id matches the current row's id MUST be
                # the thread whose balance input is reflected in the current
                # row. This catches the class of bug where the retry helper
                # accidentally overwrites the winner's balance with the
                # loser's value.
                current_id = current_row["id"]
                if results["a"] == current_id:
                    expected_balance = balance_thread_a
                elif results["b"] == current_id:
                    expected_balance = balance_thread_b
                else:
                    pytest.fail(
                        f"iteration {iteration}: current row id={current_id} "
                        f"matches neither thread's returned id "
                        f"(a={results['a']}, b={results['b']})"
                    )
                assert current_row["balance"] == expected_balance, (
                    f"iteration {iteration}: thread-balance attribution "
                    f"mismatch. Current row id={current_id} should have "
                    f"balance={expected_balance}, got {current_row['balance']}"
                )

        # After all iterations: assert the retry path actually fired at
        # least once. The retry helper logs a WARNING through the
        # logger_override (crud_account's module logger) whenever attempt 1
        # trips the partial unique index. If this assertion fails, the
        # threads are serializing every iteration and the race is not being
        # exercised -- we would be measuring the happy path while claiming
        # coverage of the retry path.
        retry_warnings = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING
            and "SCD partial-unique-index conflict" in r.getMessage()
        ]
        assert len(retry_warnings) >= 1, (
            f"Race test ran {num_iterations} iterations without firing the "
            f"retry path. The threads are serializing and the test is "
            f"providing false coverage. Either increase iteration count, "
            f"shorten the barrier release timing, or inject a deterministic "
            f"delay to force the race."
        )
