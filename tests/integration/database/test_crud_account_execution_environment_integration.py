"""
Integration tests for account_balance.execution_environment (Migration 0051).

These tests cover the post-#622+#686 synthesis behavior of crud_account:
the new required execution_environment parameter, the composite partial
unique index that allows live + paper coexistence, the SCD retry helper's
continued correctness post-migration, and the validation guard.

Test groups:
    - TestExecutionEnvironmentBasics: positive cases for the new column
    - TestParallelEnvironments: live and paper coexistence for same platform
    - TestExecutionEnvironmentValidation: typo defense at the CRUD layer
    - TestRetryHelperPostMigration: the SCD retry helper still fires
      correctly on the composite-key constraint

Migration round-trip is verified manually by the PM during application of
this PR (alembic upgrade head -> downgrade -1 -> upgrade head against the
populated dev DB). An automated round-trip test would require subprocess
invocation of alembic from inside a testcontainer fixture, which is
flaky-prone — see PR description for the manual verification record.

Reference:
    - Issue #622 (account_balance missing execution_environment column)
    - Issue #686 (PositionManager.open_position drops execution_environment)
    - findings_622_686_synthesis.md
    - Migration 0051

Markers:
    @pytest.mark.integration: real DB, ephemeral testcontainer per ADR-057
    @pytest.mark.race: race tests skip in CI (use _is_ci pattern)
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from typing import Any

import pytest

from precog.database.connection import get_cursor
from precog.database.crud_account import (
    create_account_balance,
    update_account_balance_with_versioning,
)

# Race tests skip in CI per ADR-061 — shared runners cause threading flakes
_is_ci = os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"


# =============================================================================
# Shared platform setup
# =============================================================================


@pytest.fixture
def exec_env_test_platform(db_pool: Any) -> Any:
    """Create a unique platform for exec-env tests; clean up after.

    Each test that mutates account_balance MUST clean up its own rows in
    teardown via this fixture.
    """
    platform_id = "exec-env-test-platform"

    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO platforms (
                platform_id, platform_type, display_name, base_url, status
            )
            VALUES (%s, 'trading', 'Exec Env Test Platform',
                    'https://exec-env-test.example.com', 'active')
            ON CONFLICT (platform_id) DO NOTHING
            """,
            (platform_id,),
        )
        cur.execute("DELETE FROM account_balance WHERE platform_id = %s", (platform_id,))

    yield platform_id

    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM account_balance WHERE platform_id = %s", (platform_id,))


# =============================================================================
# POSITIVE: basic creation paths
# =============================================================================


@pytest.mark.integration
class TestExecutionEnvironmentBasics:
    """Verify the new column is written and read correctly."""

    def test_create_account_balance_persists_execution_environment(
        self, exec_env_test_platform: str
    ) -> None:
        """create_account_balance writes the value to the new column."""
        balance_id = create_account_balance(
            platform_id=exec_env_test_platform,
            balance=Decimal("1000.0000"),
            execution_environment="paper",
            currency="USD",
        )
        assert balance_id is not None

        with get_cursor(commit=False) as cur:
            cur.execute(
                "SELECT execution_environment, balance, row_current_ind "
                "FROM account_balance WHERE id = %s",
                (balance_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["execution_environment"] == "paper"
        assert row["balance"] == Decimal("1000.0000")
        assert row["row_current_ind"] is True

    def test_update_versioning_persists_execution_environment(
        self, exec_env_test_platform: str
    ) -> None:
        """update_account_balance_with_versioning writes the value on insert."""
        balance_id = update_account_balance_with_versioning(
            platform_id=exec_env_test_platform,
            new_balance=Decimal("500.0000"),
            execution_environment="live",
            currency="USD",
        )
        assert balance_id is not None

        with get_cursor(commit=False) as cur:
            cur.execute(
                "SELECT execution_environment FROM account_balance WHERE id = %s",
                (balance_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["execution_environment"] == "live"


# =============================================================================
# POSITIVE: live + paper coexistence
# =============================================================================


@pytest.mark.integration
class TestParallelEnvironments:
    """Verify the composite unique index allows live + paper coexistence."""

    def test_live_and_paper_coexist_as_current(self, exec_env_test_platform: str) -> None:
        """One live current row + one paper current row = legal post-0051.

        Pre-migration this would have violated the single-column partial
        unique index on (platform_id) WHERE row_current_ind. Post-migration
        the composite index (platform_id, execution_environment) WHERE
        row_current_ind allows the two rows to coexist as current.
        """
        live_id = update_account_balance_with_versioning(
            platform_id=exec_env_test_platform,
            new_balance=Decimal("2500.0000"),
            execution_environment="live",
        )
        paper_id = update_account_balance_with_versioning(
            platform_id=exec_env_test_platform,
            new_balance=Decimal("9999.0000"),
            execution_environment="paper",
        )
        assert live_id != paper_id

        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT execution_environment, balance, row_current_ind
                FROM account_balance
                WHERE platform_id = %s AND row_current_ind = TRUE
                ORDER BY execution_environment
                """,
                (exec_env_test_platform,),
            )
            rows = cur.fetchall()

        assert len(rows) == 2, f"expected 2 current rows, got {len(rows)}: {rows}"
        envs = [r["execution_environment"] for r in rows]
        assert envs == ["live", "paper"]
        balances_by_env = {r["execution_environment"]: r["balance"] for r in rows}
        assert balances_by_env["live"] == Decimal("2500.0000")
        assert balances_by_env["paper"] == Decimal("9999.0000")

    def test_update_one_env_does_not_close_other(self, exec_env_test_platform: str) -> None:
        """Updating live balance must not affect the current paper row.

        Verifies the FOR UPDATE lock and close query are both scoped by
        execution_environment, not just platform_id. A bug here would
        manifest as a paper row being silently closed when a live update
        runs (cross-environment write contamination).
        """
        live_id_1 = update_account_balance_with_versioning(
            platform_id=exec_env_test_platform,
            new_balance=Decimal("100.0000"),
            execution_environment="live",
        )
        paper_id_1 = update_account_balance_with_versioning(
            platform_id=exec_env_test_platform,
            new_balance=Decimal("200.0000"),
            execution_environment="paper",
        )

        # Now update only the live balance.
        live_id_2 = update_account_balance_with_versioning(
            platform_id=exec_env_test_platform,
            new_balance=Decimal("150.0000"),
            execution_environment="live",
        )
        assert live_id_2 != live_id_1

        with get_cursor(commit=False) as cur:
            # The original live row must be historical.
            cur.execute(
                "SELECT row_current_ind FROM account_balance WHERE id = %s",
                (live_id_1,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row["row_current_ind"] is False, (
                "the original live row should be closed by the live update"
            )

            # The original paper row must STILL be current.
            cur.execute(
                "SELECT row_current_ind FROM account_balance WHERE id = %s",
                (paper_id_1,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row["row_current_ind"] is True, (
                "the paper row must NOT be closed by a live update -- this is "
                "the cross-environment contamination bug class this migration "
                "exists to prevent."
            )


# =============================================================================
# NEGATIVE: validation
# =============================================================================


@pytest.mark.integration
class TestExecutionEnvironmentValidation:
    """Typo-defense guard at the CRUD layer."""

    def test_create_rejects_invalid_string(self, exec_env_test_platform: str) -> None:
        """'Live' (wrong case) must raise ValueError before any DB interaction."""
        with pytest.raises(ValueError, match="Invalid execution_environment"):
            create_account_balance(
                platform_id=exec_env_test_platform,
                balance=Decimal("1000.0000"),
                execution_environment="Live",  # type: ignore[arg-type]
            )

        # Verify nothing was written.
        with get_cursor(commit=False) as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM account_balance WHERE platform_id = %s",
                (exec_env_test_platform,),
            )
            row = cur.fetchone()
        assert row is not None
        assert row["n"] == 0

    def test_update_rejects_invalid_string(self, exec_env_test_platform: str) -> None:
        """'demo' (wrong vocabulary) must raise ValueError before retry helper."""
        with pytest.raises(ValueError, match="Invalid execution_environment"):
            update_account_balance_with_versioning(
                platform_id=exec_env_test_platform,
                new_balance=Decimal("1000.0000"),
                execution_environment="demo",  # type: ignore[arg-type]
            )

    def test_create_accepts_unknown_tombstone(self, exec_env_test_platform: str) -> None:
        """'unknown' is a valid value reserved for forensic backfills."""
        balance_id = create_account_balance(
            platform_id=exec_env_test_platform,
            balance=Decimal("0.0000"),
            execution_environment="unknown",
        )
        assert balance_id is not None

        with get_cursor(commit=False) as cur:
            cur.execute(
                "SELECT execution_environment FROM account_balance WHERE id = %s",
                (balance_id,),
            )
            row = cur.fetchone()
        assert row is not None
        assert row["execution_environment"] == "unknown"


# =============================================================================
# NEGATIVE: SCD retry helper still fires
# =============================================================================


@pytest.mark.integration
@pytest.mark.race
@pytest.mark.skipif(_is_ci, reason="Race tests hang in CI per ADR-061")
class TestRetryHelperPostMigration:
    """Verify the retry helper continues to discriminate by constraint name.

    The new composite partial unique index keeps the SAME name
    (idx_balance_unique_current). The retry helper inside
    update_account_balance_with_versioning matches on the constraint name
    string, so the retry path must continue to work after the migration.
    """

    def test_concurrent_first_insert_same_env_resolves(self, exec_env_test_platform: str) -> None:
        """Two threads writing the SAME env hit the retry helper."""
        # Clean state for first-insert race.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM account_balance WHERE platform_id = %s",
                (exec_env_test_platform,),
            )

        barrier = threading.Barrier(parties=2)
        results: dict[str, int | None] = {"a": None, "b": None}
        errors: dict[str, Exception | None] = {"a": None, "b": None}

        def attempt(label: str, balance: Decimal) -> None:
            try:
                barrier.wait(timeout=10.0)
                bid = update_account_balance_with_versioning(
                    platform_id=exec_env_test_platform,
                    new_balance=balance,
                    execution_environment="paper",
                )
                results[label] = bid
            except Exception as exc:
                errors[label] = exc

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(attempt, "a", Decimal("100.0000")),
                executor.submit(attempt, "b", Decimal("200.0000")),
            ]
            for future in as_completed(futures):
                future.result()

        assert errors["a"] is None, f"thread A raised: {errors['a']!r}"
        assert errors["b"] is None, f"thread B raised: {errors['b']!r}"
        assert results["a"] is not None
        assert results["b"] is not None

        # Both rows must exist; exactly one must be current; both must be 'paper'.
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT execution_environment, row_current_ind
                FROM account_balance
                WHERE platform_id = %s
                ORDER BY row_start_ts ASC
                """,
                (exec_env_test_platform,),
            )
            rows = cur.fetchall()
        assert len(rows) == 2
        assert all(r["execution_environment"] == "paper" for r in rows)
        current_count = sum(1 for r in rows if r["row_current_ind"])
        assert current_count == 1, (
            f"expected exactly one current row after retry, got {current_count}"
        )

    def test_concurrent_first_insert_different_envs_no_retry(
        self, exec_env_test_platform: str
    ) -> None:
        """Two threads writing DIFFERENT envs do NOT hit the retry helper.

        Pre-migration, the single-column unique index would have forced one
        thread to retry. Post-migration the composite key allows both to
        succeed in parallel without any retry. Verifies the new index does
        not over-serialize cross-environment writes.
        """
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM account_balance WHERE platform_id = %s",
                (exec_env_test_platform,),
            )

        barrier = threading.Barrier(parties=2)
        results: dict[str, int | None] = {"live": None, "paper": None}
        errors: dict[str, Exception | None] = {"live": None, "paper": None}

        def attempt(env: str, balance: Decimal) -> None:
            try:
                barrier.wait(timeout=10.0)
                bid = update_account_balance_with_versioning(
                    platform_id=exec_env_test_platform,
                    new_balance=balance,
                    execution_environment=env,  # type: ignore[arg-type]
                )
                results[env] = bid
            except Exception as exc:
                errors[env] = exc

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(attempt, "live", Decimal("1.0000")),
                executor.submit(attempt, "paper", Decimal("2.0000")),
            ]
            for future in as_completed(futures):
                future.result()

        assert errors["live"] is None
        assert errors["paper"] is None
        assert results["live"] != results["paper"]

        # Both rows current; one each per environment.
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT execution_environment, row_current_ind
                FROM account_balance
                WHERE platform_id = %s AND row_current_ind = TRUE
                """,
                (exec_env_test_platform,),
            )
            rows = cur.fetchall()
        envs = sorted(r["execution_environment"] for r in rows)
        assert envs == ["live", "paper"], f"expected ['live', 'paper'], got {envs}"
