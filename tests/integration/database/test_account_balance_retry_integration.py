"""
CI integration tests for ``update_account_balance_with_versioning`` against
a real PostgreSQL database.

Issue #613: the SCD race-prevention retry helper was originally covered by
(a) unit tests that mock the cursor and (b) a multi-threaded race test that
is skipped in CI. Marvin Scenario 35 flagged the gap: nothing CI-visible
exercised the helper composing with the real ``get_cursor`` rollback path,
connection pool, and psycopg2 transaction state.

This file fills that gap with single-threaded integration tests that run
in CI (NO ``_is_ci`` skip). These are NOT race tests -- they verify:

    1. First-insert path -- the helper's ``operation`` closure executes
       cleanly against a real DB, a current row is created, row_current_ind
       is TRUE.
    2. Update-with-versioning path -- a second call closes the prior row,
       inserts a new current row, and preserves Pattern 49 temporal
       continuity (historical.row_end_ts == current.row_start_ts).
    3. Decimal preservation -- the returned balance is Decimal, not float,
       across the retry-wrapped code path.

Race-path integration coverage (actually triggering the retry helper inside
a real transaction) is provided by
``tests/race/test_account_balance_concurrent_first_insert.py``, which runs
locally and nightly. The combination of unit tests (mocked helper logic),
this file (single-threaded real-DB composition), and the race test
(concurrent retry path) gives full defense in depth without depending on
CI-hostile threading.

Reference:
    - Issue #613
    - Migration 0049 (idx_balance_unique_current partial unique index)
    - crud_shared.retry_on_scd_unique_conflict
    - Pattern 49 (SCD Race Prevention)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from precog.database.connection import get_cursor
from precog.database.crud_account import update_account_balance_with_versioning

# Platform identifier reserved for this integration test. Keep distinct from
# the race test's ``test_race_613`` so parallel runs do not collide. The
# ``test_`` prefix aligns with ``clean_test_data``'s cleanup regex so a stray
# row will not survive suite cleanup, but we also manage our own teardown
# explicitly to keep the test hermetic.
TEST_PLATFORM = "test_retry_integration_613"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def retry_integration_platform(db_pool: Any) -> Any:
    """Create a clean test platform and tear down after each test.

    Uses its own ``get_cursor(commit=True)`` blocks (NOT the suite-wide
    ``clean_test_data`` SAVEPOINT-style rollback fixture), because
    ``update_account_balance_with_versioning`` commits real rows that
    would survive a transaction rollback.
    """
    # Setup: clean any leftover state and ensure the platform row exists.
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM settlements WHERE platform_id = %s",
            (TEST_PLATFORM,),
        )
        cur.execute(
            "DELETE FROM account_balance WHERE platform_id = %s",
            (TEST_PLATFORM,),
        )
        cur.execute(
            """
            INSERT INTO platforms (
                platform_id, platform_type, display_name, base_url, status
            )
            VALUES (
                %s, 'trading', 'Retry Integration Test Platform 613',
                'https://retry-integration-613.test', 'active'
            )
            ON CONFLICT (platform_id) DO NOTHING
            """,
            (TEST_PLATFORM,),
        )

    yield TEST_PLATFORM

    # Teardown: remove all rows this test touched.
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM settlements WHERE platform_id = %s",
                (TEST_PLATFORM,),
            )
            cur.execute(
                "DELETE FROM account_balance WHERE platform_id = %s",
                (TEST_PLATFORM,),
            )
            cur.execute(
                "DELETE FROM platforms WHERE platform_id = %s",
                (TEST_PLATFORM,),
            )
    except Exception:
        # Best-effort cleanup; do not mask the actual test outcome.
        pass


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.integration
class TestAccountBalanceRetryIntegration:
    """Single-threaded integration coverage for the retry-wrapped path."""

    def test_first_insert_creates_current_row(self, retry_integration_platform: str) -> None:
        """First call with no prior current row inserts a fresh current row.

        Verifies the retry helper's ``operation`` closure composes with a
        real ``get_cursor(commit=True)`` block, commits cleanly, and leaves
        exactly one row with ``row_current_ind = TRUE``.
        """
        balance = Decimal("1234.5678")

        balance_id = update_account_balance_with_versioning(
            platform_id=retry_integration_platform,
            new_balance=balance,
            currency="USD",
        )

        assert balance_id is not None
        assert isinstance(balance_id, int)

        # Verify exactly one current row with the expected state.
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT id, balance, currency, row_current_ind,
                       row_start_ts, row_end_ts
                FROM account_balance
                WHERE platform_id = %s
                ORDER BY row_start_ts ASC
                """,
                (retry_integration_platform,),
            )
            rows = cur.fetchall()

        assert len(rows) == 1, f"expected exactly one row, found {len(rows)}: {rows}"
        row = rows[0]
        assert row["id"] == balance_id
        assert row["balance"] == balance
        assert isinstance(row["balance"], Decimal), "balance must be Decimal (Pattern 1), not float"
        assert row["currency"] == "USD"
        assert row["row_current_ind"] is True
        assert row["row_start_ts"] is not None
        assert row["row_end_ts"] is None

    def test_update_versioning_closes_prior_and_opens_new(
        self, retry_integration_platform: str
    ) -> None:
        """Second call closes the prior current row and inserts a new one.

        Verifies Pattern 49 temporal continuity
        (historical.row_end_ts == current.row_start_ts) across a
        retry-wrapped update composed against the real database.
        """
        initial_balance = Decimal("1000.0000")
        updated_balance = Decimal("1500.2500")

        first_id = update_account_balance_with_versioning(
            platform_id=retry_integration_platform,
            new_balance=initial_balance,
            currency="USD",
        )
        assert first_id is not None

        second_id = update_account_balance_with_versioning(
            platform_id=retry_integration_platform,
            new_balance=updated_balance,
            currency="USD",
        )
        assert second_id is not None
        assert second_id != first_id, "second call must insert a new row with a distinct id"

        # Verify both rows exist, one historical and one current, with
        # temporal continuity.
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT id, balance, row_current_ind, row_start_ts, row_end_ts
                FROM account_balance
                WHERE platform_id = %s
                ORDER BY row_start_ts ASC
                """,
                (retry_integration_platform,),
            )
            rows = cur.fetchall()

        assert len(rows) == 2, f"expected exactly two rows after update, found {len(rows)}: {rows}"

        historical_rows = [r for r in rows if not r["row_current_ind"]]
        current_rows = [r for r in rows if r["row_current_ind"]]

        assert len(historical_rows) == 1, (
            f"expected exactly one historical row, found {len(historical_rows)}"
        )
        assert len(current_rows) == 1, (
            f"expected exactly one current row, found {len(current_rows)}"
        )

        historical = historical_rows[0]
        current = current_rows[0]

        # Historical row has row_end_ts; current row does not.
        assert historical["row_end_ts"] is not None, "historical row must have row_end_ts populated"
        assert current["row_end_ts"] is None, "current row must have row_end_ts NULL"

        # Historical row carries the first balance; current row carries the
        # updated balance. Decimal preservation checked on both.
        assert historical["balance"] == initial_balance
        assert current["balance"] == updated_balance
        assert isinstance(historical["balance"], Decimal)
        assert isinstance(current["balance"], Decimal)

        # Row IDs wire up correctly to the two returned values.
        assert historical["id"] == first_id
        assert current["id"] == second_id

        # Pattern 49 temporal continuity: historical.row_end_ts must equal
        # current.row_start_ts so the version chain has no gap and no
        # backward interval.
        assert historical["row_end_ts"] == current["row_start_ts"], (
            f"temporal continuity violation: "
            f"historical.row_end_ts={historical['row_end_ts']} != "
            f"current.row_start_ts={current['row_start_ts']}"
        )

    def test_rejects_non_decimal_balance(self, retry_integration_platform: str) -> None:
        """The Decimal validation guard must fire BEFORE any DB interaction.

        Ensures the retry-wrapped function preserves the type-guard contract
        end to end, so float contamination cannot slip through the retry
        path into a real INSERT.
        """
        with pytest.raises(ValueError, match="Decimal"):
            update_account_balance_with_versioning(
                platform_id=retry_integration_platform,
                new_balance=1000.0,  # type: ignore[arg-type]
                currency="USD",
            )

        # Verify no row was created -- the guard fires before the retry
        # helper's operation() is ever invoked.
        with get_cursor(commit=False) as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM account_balance WHERE platform_id = %s",
                (retry_integration_platform,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["n"] == 0, "no rows should exist after a guard rejection"
