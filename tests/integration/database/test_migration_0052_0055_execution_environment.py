"""Integration tests for migrations 0052-0055 (execution_environment columns).

Phase A of Issue #691 -- finishes the cross-environment-contamination
architecture that PR #690 / migration 0051 started. These tests verify
the POST-MIGRATION DDL shape of the 4 target tables:

    * account_ledger (migration 0052) -- 4-value tombstone
    * settlements    (migration 0053) -- 3-value, default 'live'
    * position_exits (migration 0054) -- 4-value tombstone
    * exit_attempts  (migration 0055) -- 4-value tombstone

Test groups:
    - TestExecutionEnvironmentColumnShape: column exists, NOT NULL,
      no server default after Step 4 drops it, correct CHECK constraint
      values (verifies the intentional 4-vs-3 asymmetry)
    - TestInsertValidValues: every allowed value on each table INSERTs
      successfully and round-trips via SELECT
    - TestCheckConstraintRejects: invalid values are rejected at the
      DB layer (belt-and-suspenders even if Phase B Python validators
      are bypassed)
    - TestNotNullEnforcement: an INSERT that omits the column must fail

Migration round-trip (upgrade -> downgrade -> re-upgrade) is verified
by the PM during build via manual alembic invocation against a populated
test DB. An automated subprocess-invocation round-trip test would be
flaky in the CI testcontainer model (see the docstring of
test_crud_account_execution_environment_integration.py for the same
rationale applied to migration 0051).

Reference:
    - Issue #691 (Phase A: schema migrations; Phase B: CRUD/read paths)
    - Migration 0051 (account_balance.execution_environment, PR #690)
    - Migrations 0052-0055 (this PR)
    - docs/database/RATIONALE_MIGRATION_0051.md
    - ADR-107

Markers:
    @pytest.mark.integration: real DB required (testcontainer per ADR-057)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import psycopg2
import pytest

from precog.database.connection import get_cursor

# =============================================================================
# Table / CHECK-constraint matrix
# =============================================================================

# 4-value tombstone tables: pre-migration historical rows have ambiguous
# provenance and must be distinguishable from post-migration rows.
TOMBSTONE_TABLES = ("account_ledger", "position_exits", "exit_attempts")
TOMBSTONE_VALUES = ("live", "paper", "backtest", "unknown")

# 3-value tables: historical rows are definitionally live (settlements come
# exclusively from Kalshi's live settlement feed in the current codebase).
NON_TOMBSTONE_TABLES = ("settlements",)
NON_TOMBSTONE_VALUES = ("live", "paper", "backtest")

ALL_TARGET_TABLES = TOMBSTONE_TABLES + NON_TOMBSTONE_TABLES

# Constraint name map (for CHECK-definition assertions).
CONSTRAINT_NAMES = {
    "account_ledger": "chk_account_ledger_exec_env",
    "settlements": "chk_settlements_exec_env",
    "position_exits": "chk_position_exits_exec_env",
    "exit_attempts": "chk_exit_attempts_exec_env",
}


# =============================================================================
# Shared fixtures: a platform + market + position that the append-only
# children can reference via FK.
# =============================================================================


@pytest.fixture
def migration_test_platform(db_pool: Any) -> Any:
    """Create an isolated platform + market + position.

    Returns (platform_id, market_internal_id, position_internal_id).
    Children of position_internal_id (position_exits, exit_attempts) can
    reference it. Children of platform_id (account_ledger, settlements)
    can reference it directly. Cleanup deletes all 4 tables + position +
    market + platform in reverse FK order.
    """
    platform_id = "mig-0052-55-test-plat"

    with get_cursor(commit=True) as cur:
        # Defensive cleanup of any prior run.
        cur.execute(
            "DELETE FROM exit_attempts WHERE position_internal_id IN "
            "(SELECT id FROM positions WHERE platform_id = %s)",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM position_exits WHERE position_internal_id IN "
            "(SELECT id FROM positions WHERE platform_id = %s)",
            (platform_id,),
        )
        cur.execute("DELETE FROM account_ledger WHERE platform_id = %s", (platform_id,))
        cur.execute("DELETE FROM settlements WHERE platform_id = %s", (platform_id,))
        cur.execute("DELETE FROM positions WHERE platform_id = %s", (platform_id,))
        cur.execute("DELETE FROM markets WHERE platform_id = %s", (platform_id,))
        cur.execute("DELETE FROM platforms WHERE platform_id = %s", (platform_id,))

        # Platform
        cur.execute(
            """
            INSERT INTO platforms (
                platform_id, platform_type, display_name, base_url, status
            )
            VALUES (%s, 'trading', 'Migration 52-55 Test Plat',
                    'https://mig-test.example.com', 'active')
            """,
            (platform_id,),
        )

        # Market (FK target for settlements via market_internal_id)
        cur.execute(
            """
            INSERT INTO markets (
                platform_id, external_id, ticker, title, market_type, status
            )
            VALUES (%s, 'MIG-52-55-TEST', 'MIG-52-55-TEST',
                    'Migration 0052-0055 test market', 'binary', 'open')
            RETURNING id
            """,
            (platform_id,),
        )
        market_internal_id = cur.fetchone()["id"]

        # Position (FK target for position_exits / exit_attempts via
        # position_internal_id). Uses a unique business key so concurrent
        # test runs don't collide.
        cur.execute(
            """
            INSERT INTO positions (
                position_id, platform_id, market_internal_id, side, quantity,
                entry_price, current_price, status, entry_time, last_check_time,
                row_current_ind, row_start_ts, execution_environment
            )
            VALUES (
                %s, %s, %s, 'YES', 10,
                %s, %s, 'open', NOW(), NOW(),
                TRUE, NOW(), 'live'
            )
            RETURNING id
            """,
            (
                "MIG-52-55-POS",
                platform_id,
                market_internal_id,
                Decimal("0.5000"),
                Decimal("0.5000"),
            ),
        )
        position_internal_id = cur.fetchone()["id"]

    yield platform_id, market_internal_id, position_internal_id

    # Teardown in reverse FK order.
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM exit_attempts WHERE position_internal_id = %s",
            (position_internal_id,),
        )
        cur.execute(
            "DELETE FROM position_exits WHERE position_internal_id = %s",
            (position_internal_id,),
        )
        cur.execute("DELETE FROM account_ledger WHERE platform_id = %s", (platform_id,))
        cur.execute("DELETE FROM settlements WHERE platform_id = %s", (platform_id,))
        cur.execute("DELETE FROM positions WHERE id = %s", (position_internal_id,))
        cur.execute("DELETE FROM markets WHERE id = %s", (market_internal_id,))
        cur.execute("DELETE FROM platforms WHERE platform_id = %s", (platform_id,))


# =============================================================================
# Helper: table-specific INSERT builder
# =============================================================================


def _insert_row(
    cur: Any,
    table: str,
    execution_environment: str | None,
    *,
    platform_id: str,
    market_internal_id: int,
    position_internal_id: int,
) -> None:
    """INSERT a minimal valid row into one of the 4 target tables.

    If execution_environment is None, OMIT the column entirely (used to
    verify NOT NULL enforcement — since migrations 0052-0055 drop the
    server_default, omitting the column must raise NotNullViolation).
    """
    if table == "account_ledger":
        if execution_environment is None:
            cur.execute(
                """
                INSERT INTO account_ledger (
                    platform_id, transaction_type, amount, running_balance
                )
                VALUES (%s, 'deposit', 100.0000, 100.0000)
                """,
                (platform_id,),
            )
        else:
            cur.execute(
                """
                INSERT INTO account_ledger (
                    platform_id, transaction_type, amount, running_balance,
                    execution_environment
                )
                VALUES (%s, 'deposit', 100.0000, 100.0000, %s)
                """,
                (platform_id, execution_environment),
            )
    elif table == "settlements":
        if execution_environment is None:
            cur.execute(
                """
                INSERT INTO settlements (
                    platform_id, market_internal_id, outcome, payout
                )
                VALUES (%s, %s, 'yes', 10.0000)
                """,
                (platform_id, market_internal_id),
            )
        else:
            cur.execute(
                """
                INSERT INTO settlements (
                    platform_id, market_internal_id, outcome, payout,
                    execution_environment
                )
                VALUES (%s, %s, 'yes', 10.0000, %s)
                """,
                (platform_id, market_internal_id, execution_environment),
            )
    elif table == "position_exits":
        if execution_environment is None:
            cur.execute(
                """
                INSERT INTO position_exits (
                    position_internal_id, exit_reason, exit_price,
                    quantity_exited, realized_pnl
                )
                VALUES (%s, 'stop_loss', 0.4500, 5, -0.2500)
                """,
                (position_internal_id,),
            )
        else:
            cur.execute(
                """
                INSERT INTO position_exits (
                    position_internal_id, exit_reason, exit_price,
                    quantity_exited, realized_pnl, execution_environment
                )
                VALUES (%s, 'stop_loss', 0.4500, 5, -0.2500, %s)
                """,
                (position_internal_id, execution_environment),
            )
    elif table == "exit_attempts":
        if execution_environment is None:
            cur.execute(
                """
                INSERT INTO exit_attempts (
                    position_internal_id, exit_reason, attempted_price,
                    success, failure_reason
                )
                VALUES (%s, 'stop_loss', 0.4500, FALSE, 'market_suspended')
                """,
                (position_internal_id,),
            )
        else:
            cur.execute(
                """
                INSERT INTO exit_attempts (
                    position_internal_id, exit_reason, attempted_price,
                    success, failure_reason, execution_environment
                )
                VALUES (%s, 'stop_loss', 0.4500, FALSE, 'market_suspended', %s)
                """,
                (position_internal_id, execution_environment),
            )
    else:
        raise ValueError(f"unknown table: {table}")


# =============================================================================
# TestExecutionEnvironmentColumnShape
# =============================================================================


@pytest.mark.integration
class TestExecutionEnvironmentColumnShape:
    """Column exists, NOT NULL, server default dropped, CHECK present."""

    @pytest.mark.parametrize("table", ALL_TARGET_TABLES)
    def test_column_exists_and_not_null(self, db_pool: Any, table: str) -> None:
        """execution_environment column present, VARCHAR(20), NOT NULL."""
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT column_name, data_type, character_maximum_length,
                       is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                  AND column_name = 'execution_environment'
                """,
                (table,),
            )
            row = cur.fetchone()

        assert row is not None, f"{table}.execution_environment column missing"
        assert row["data_type"] == "character varying"
        assert row["character_maximum_length"] == 20
        assert row["is_nullable"] == "NO"
        # Step 4 of each migration drops the server_default after backfill.
        # Phase B will make the CRUD signature REQUIRED; the absence of a
        # DDL default is the belt-and-suspenders that closes the
        # "optional-default 'live'" precedent that caused #622/#686.
        assert row["column_default"] is None, (
            f"{table}.execution_environment still has a server_default "
            f"({row['column_default']!r}); migration step 4 should have "
            f"dropped it."
        )

    @pytest.mark.parametrize("table", TOMBSTONE_TABLES)
    def test_tombstone_tables_allow_4_values(self, db_pool: Any, table: str) -> None:
        """Tombstone tables accept the 4-value set (including 'unknown')."""
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT pg_get_constraintdef(c.oid) AS defn
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                WHERE t.relname = %s AND c.conname = %s
                """,
                (table, CONSTRAINT_NAMES[table]),
            )
            row = cur.fetchone()

        assert row is not None, f"{table} missing {CONSTRAINT_NAMES[table]}"
        defn = row["defn"]
        for value in TOMBSTONE_VALUES:
            assert f"'{value}'" in defn, f"{table} CHECK constraint missing value '{value}': {defn}"

    @pytest.mark.parametrize("table", NON_TOMBSTONE_TABLES)
    def test_non_tombstone_tables_allow_3_values_only(self, db_pool: Any, table: str) -> None:
        """Non-tombstone tables accept only the 3-value set (NO 'unknown').

        Verifies the intentional 4-vs-3 asymmetry documented in
        RATIONALE_MIGRATION_0051.md. Trades, positions, orders, edges,
        and settlements belong to the TRADE_POSITION domain and do NOT
        reserve 'unknown'. A regression that accidentally added 'unknown'
        to this CHECK would silently weaken the forensic honesty guard.
        """
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT pg_get_constraintdef(c.oid) AS defn
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                WHERE t.relname = %s AND c.conname = %s
                """,
                (table, CONSTRAINT_NAMES[table]),
            )
            row = cur.fetchone()

        assert row is not None, f"{table} missing {CONSTRAINT_NAMES[table]}"
        defn = row["defn"]
        for value in NON_TOMBSTONE_VALUES:
            assert f"'{value}'" in defn, f"{table} CHECK missing value '{value}': {defn}"
        assert "'unknown'" not in defn, (
            f"{table} CHECK unexpectedly contains 'unknown' -- the 4-vs-3 "
            f"asymmetry has been violated. See RATIONALE_MIGRATION_0051.md."
        )


# =============================================================================
# TestInsertValidValues
# =============================================================================


@pytest.mark.integration
class TestInsertValidValues:
    """Every allowed value inserts cleanly and round-trips via SELECT."""

    def test_account_ledger_accepts_all_tombstone_values(
        self, migration_test_platform: tuple[str, int, int]
    ) -> None:
        platform_id, market_id, position_id = migration_test_platform
        for env in TOMBSTONE_VALUES:
            with get_cursor(commit=True) as cur:
                _insert_row(
                    cur,
                    "account_ledger",
                    env,
                    platform_id=platform_id,
                    market_internal_id=market_id,
                    position_internal_id=position_id,
                )

        with get_cursor(commit=False) as cur:
            cur.execute(
                "SELECT execution_environment FROM account_ledger "
                "WHERE platform_id = %s ORDER BY id",
                (platform_id,),
            )
            envs = [r["execution_environment"] for r in cur.fetchall()]
        assert sorted(envs) == sorted(TOMBSTONE_VALUES), (
            f"expected round-trip of {TOMBSTONE_VALUES}, got {envs}"
        )

    def test_settlements_accepts_3_values(
        self, migration_test_platform: tuple[str, int, int]
    ) -> None:
        platform_id, market_id, position_id = migration_test_platform
        for env in NON_TOMBSTONE_VALUES:
            with get_cursor(commit=True) as cur:
                _insert_row(
                    cur,
                    "settlements",
                    env,
                    platform_id=platform_id,
                    market_internal_id=market_id,
                    position_internal_id=position_id,
                )

        with get_cursor(commit=False) as cur:
            cur.execute(
                "SELECT execution_environment FROM settlements WHERE platform_id = %s ORDER BY id",
                (platform_id,),
            )
            envs = [r["execution_environment"] for r in cur.fetchall()]
        assert sorted(envs) == sorted(NON_TOMBSTONE_VALUES)

    def test_position_exits_accepts_all_tombstone_values(
        self, migration_test_platform: tuple[str, int, int]
    ) -> None:
        platform_id, market_id, position_id = migration_test_platform
        for env in TOMBSTONE_VALUES:
            with get_cursor(commit=True) as cur:
                _insert_row(
                    cur,
                    "position_exits",
                    env,
                    platform_id=platform_id,
                    market_internal_id=market_id,
                    position_internal_id=position_id,
                )

        with get_cursor(commit=False) as cur:
            cur.execute(
                "SELECT execution_environment FROM position_exits "
                "WHERE position_internal_id = %s ORDER BY exit_id",
                (position_id,),
            )
            envs = [r["execution_environment"] for r in cur.fetchall()]
        assert sorted(envs) == sorted(TOMBSTONE_VALUES)

    def test_exit_attempts_accepts_all_tombstone_values(
        self, migration_test_platform: tuple[str, int, int]
    ) -> None:
        platform_id, market_id, position_id = migration_test_platform
        for env in TOMBSTONE_VALUES:
            with get_cursor(commit=True) as cur:
                _insert_row(
                    cur,
                    "exit_attempts",
                    env,
                    platform_id=platform_id,
                    market_internal_id=market_id,
                    position_internal_id=position_id,
                )

        with get_cursor(commit=False) as cur:
            cur.execute(
                "SELECT execution_environment FROM exit_attempts "
                "WHERE position_internal_id = %s ORDER BY attempt_id",
                (position_id,),
            )
            envs = [r["execution_environment"] for r in cur.fetchall()]
        assert sorted(envs) == sorted(TOMBSTONE_VALUES)


# =============================================================================
# TestCheckConstraintRejects
# =============================================================================


@pytest.mark.integration
class TestCheckConstraintRejects:
    """Invalid values are rejected at the DB layer."""

    @pytest.mark.parametrize("table", ALL_TARGET_TABLES)
    def test_rejects_typo_value(
        self, migration_test_platform: tuple[str, int, int], table: str
    ) -> None:
        """'Live' (wrong case) must violate the CHECK on every table."""
        platform_id, market_id, position_id = migration_test_platform
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                _insert_row(
                    cur,
                    table,
                    "Live",  # wrong case
                    platform_id=platform_id,
                    market_internal_id=market_id,
                    position_internal_id=position_id,
                )

    @pytest.mark.parametrize("table", ALL_TARGET_TABLES)
    def test_rejects_wrong_vocabulary(
        self, migration_test_platform: tuple[str, int, int], table: str
    ) -> None:
        """'demo' (wrong vocabulary -- that's MarketMode) must violate CHECK."""
        platform_id, market_id, position_id = migration_test_platform
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                _insert_row(
                    cur,
                    table,
                    "demo",
                    platform_id=platform_id,
                    market_internal_id=market_id,
                    position_internal_id=position_id,
                )

    @pytest.mark.parametrize("table", NON_TOMBSTONE_TABLES)
    def test_settlements_rejects_unknown_tombstone(
        self, migration_test_platform: tuple[str, int, int], table: str
    ) -> None:
        """'unknown' is a tombstone reserved for BALANCE-domain tables only.

        settlements is in the TRADE_POSITION domain (3-value). A Python
        caller passing 'unknown' to create_settlement SHOULD fail at the
        Phase B per-domain frozenset check, but this test verifies the
        belt-and-suspenders DB-layer CHECK rejects it even if the Python
        layer is bypassed.
        """
        platform_id, market_id, position_id = migration_test_platform
        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_cursor(commit=True) as cur:
                _insert_row(
                    cur,
                    table,
                    "unknown",
                    platform_id=platform_id,
                    market_internal_id=market_id,
                    position_internal_id=position_id,
                )


# =============================================================================
# TestNotNullEnforcement
# =============================================================================


@pytest.mark.integration
class TestNotNullEnforcement:
    """Omitting execution_environment must fail (no server default)."""

    @pytest.mark.parametrize("table", ALL_TARGET_TABLES)
    def test_insert_without_column_violates_not_null(
        self, migration_test_platform: tuple[str, int, int], table: str
    ) -> None:
        """INSERT that omits execution_environment must raise NotNullViolation.

        Migrations 0052-0055 each drop the server_default in Step 4, so
        after the migration runs there is no fallback value. The column
        is NOT NULL. Omitting it must loudly fail at the DB layer. This
        is the belt-and-suspenders that closes the "optional-default
        'live'" precedent at the SCHEMA level even if a Python caller
        somehow bypasses the Phase B REQUIRED signature.
        """
        platform_id, market_id, position_id = migration_test_platform
        with pytest.raises(psycopg2.errors.NotNullViolation):
            with get_cursor(commit=True) as cur:
                _insert_row(
                    cur,
                    table,
                    None,  # omit column entirely
                    platform_id=platform_id,
                    market_internal_id=market_id,
                    position_internal_id=position_id,
                )
