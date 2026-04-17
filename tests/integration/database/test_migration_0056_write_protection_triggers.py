"""Integration tests for migration 0056 (write-protection triggers).

Issues: #371 (immutability), #723 (append-only)
Epic: #745 (Schema Hardening Arc, Cohort C1)

Test groups:
    - TestTriggerFunctionsExist: verify all 3 trigger functions exist in pg_proc
    - TestTriggersExist: verify all 7 triggers exist on their tables
    - TestStrategyImmutability: mutable UPDATE succeeds, immutable UPDATE raises
    - TestModelImmutability: mutable UPDATE succeeds, immutable UPDATE raises
    - TestAppendOnlyEnforcement: INSERT succeeds, UPDATE raises on all 5 tables

Markers:
    @pytest.mark.integration: real DB required (testcontainer per ADR-057)
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any

import psycopg2
import pytest

from precog.database.connection import get_cursor

# =============================================================================
# Constants
# =============================================================================

TRIGGER_FUNCTIONS = (
    "enforce_strategy_immutability",
    "enforce_model_immutability",
    "prevent_append_only_update",
)

TRIGGER_MAP = {
    "strategies": "trg_strategies_immutability",
    "probability_models": "trg_models_immutability",
    "trades": "trg_trades_append_only",
    "settlements": "trg_settlements_append_only",
    "account_ledger": "trg_account_ledger_append_only",
    "position_exits": "trg_position_exits_append_only",
    "exit_attempts": "trg_exit_attempts_append_only",
}

APPEND_ONLY_TABLES = (
    "trades",
    "settlements",
    "account_ledger",
    "position_exits",
    "exit_attempts",
)

# Unique platform_id for test isolation.
TEST_PLATFORM_ID = "mig-0056-trigger-test"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def trigger_test_scaffold(db_pool: Any) -> Any:
    """Create platform + market + position + strategy + model for trigger tests.

    Yields a dict with all surrogate IDs needed by the test table INSERTs.
    Cleans up in reverse FK order on teardown.
    """
    with get_cursor(commit=True) as cur:
        # Defensive cleanup of prior run artifacts.
        _cleanup(cur, TEST_PLATFORM_ID)

        # Platform
        cur.execute(
            """
            INSERT INTO platforms (
                platform_id, platform_type, display_name, base_url, status
            )
            VALUES (%s, 'trading', 'Migration 0056 Trigger Test',
                    'https://trigger-test.example.com', 'active')
            """,
            (TEST_PLATFORM_ID,),
        )

        # Strategy (we test trigger on this row).
        # strategy_type FK -> strategy_types(strategy_type_code); use 'value'.
        cur.execute(
            """
            INSERT INTO strategies (
                platform_id, strategy_name, strategy_version,
                strategy_type, config, status
            )
            VALUES (%s, 'trigger-test-strat', '1.0', 'value',
                    %s, 'draft')
            RETURNING strategy_id
            """,
            (TEST_PLATFORM_ID, json.dumps({"param": "original"})),
        )
        strategy_id = cur.fetchone()["strategy_id"]

        # Probability model (we test trigger on this row).
        # model_class FK -> model_classes(model_class_code); use 'elo'.
        cur.execute(
            """
            INSERT INTO probability_models (
                model_name, model_version, model_class, config, status
            )
            VALUES ('trigger-test-model', '1.0', 'elo',
                    %s, 'draft')
            RETURNING model_id
            """,
            (json.dumps({"learning_rate": "0.01"}),),
        )
        model_id = cur.fetchone()["model_id"]

        # Market (FK target for trades, settlements).  Migration 0062
        # (#791): markets.market_key is NOT NULL + UNIQUE.  Raw-SQL migration
        # test — inline the TEMP→MKT-{id} two-step.
        cur.execute(
            """
            INSERT INTO markets (
                platform_id, external_id, ticker, title, market_type, status,
                market_key
            )
            VALUES (%s, 'MIG-0056-TEST', 'MIG-0056-TEST',
                    'Migration 0056 trigger test market', 'binary', 'open', %s)
            RETURNING id
            """,
            (TEST_PLATFORM_ID, f"TEMP-{uuid.uuid4()}"),
        )
        market_id = cur.fetchone()["id"]
        cur.execute(
            "UPDATE markets SET market_key = %s WHERE id = %s",
            (f"MKT-{market_id}", market_id),
        )

        # Position (FK target for trades, position_exits, exit_attempts)
        cur.execute(
            """
            INSERT INTO positions (
                position_key, platform_id, market_id, side, quantity,
                entry_price, current_price, status, entry_time, last_check_time,
                row_current_ind, row_start_ts, execution_environment
            )
            VALUES (
                'MIG-0056-POS', %s, %s, 'YES', 10,
                %s, %s, 'open', NOW(), NOW(),
                TRUE, NOW(), 'live'
            )
            RETURNING id
            """,
            (
                TEST_PLATFORM_ID,
                market_id,
                Decimal("0.5000"),
                Decimal("0.5000"),
            ),
        )
        position_internal_id = cur.fetchone()["id"]

    yield {
        "platform_id": TEST_PLATFORM_ID,
        "strategy_id": strategy_id,
        "model_id": model_id,
        "market_id": market_id,
        "position_internal_id": position_internal_id,
    }

    # Teardown in reverse FK order.
    with get_cursor(commit=True) as cur:
        _cleanup(cur, TEST_PLATFORM_ID)


def _cleanup(cur: Any, platform_id: str) -> None:
    """Delete all test artifacts in reverse FK order."""
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
    cur.execute(
        "DELETE FROM trades WHERE platform_id = %s",
        (platform_id,),
    )
    cur.execute(
        "DELETE FROM account_ledger WHERE platform_id = %s",
        (platform_id,),
    )
    cur.execute(
        "DELETE FROM settlements WHERE platform_id = %s",
        (platform_id,),
    )
    cur.execute(
        "DELETE FROM positions WHERE platform_id = %s",
        (platform_id,),
    )
    cur.execute(
        "DELETE FROM markets WHERE platform_id = %s",
        (platform_id,),
    )
    cur.execute(
        "DELETE FROM strategies WHERE platform_id = %s",
        (platform_id,),
    )
    cur.execute(
        "DELETE FROM probability_models WHERE model_name = 'trigger-test-model'",
    )
    cur.execute(
        "DELETE FROM platforms WHERE platform_id = %s",
        (platform_id,),
    )


# =============================================================================
# Test: Trigger functions exist in pg_proc
# =============================================================================


@pytest.mark.integration
class TestTriggerFunctionsExist:
    """Verify all 3 trigger functions are installed."""

    @pytest.mark.parametrize("func_name", TRIGGER_FUNCTIONS)
    def test_function_exists(self, db_pool: Any, func_name: str) -> None:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT proname FROM pg_proc
                WHERE proname = %s
                  AND prorettype = 'trigger'::regtype
                """,
                (func_name,),
            )
            row = cur.fetchone()
            assert row is not None, f"Trigger function {func_name} not found"


# =============================================================================
# Test: Triggers exist on their tables
# =============================================================================


@pytest.mark.integration
class TestTriggersExist:
    """Verify all 7 triggers are attached to the correct tables."""

    @pytest.mark.parametrize(
        ("table_name", "trigger_name"),
        list(TRIGGER_MAP.items()),
    )
    def test_trigger_exists(self, db_pool: Any, table_name: str, trigger_name: str) -> None:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT trigger_name, event_manipulation, action_timing
                FROM information_schema.triggers
                WHERE trigger_name = %s
                  AND event_object_table = %s
                """,
                (trigger_name, table_name),
            )
            row = cur.fetchone()
            assert row is not None, f"Trigger {trigger_name} not found on {table_name}"
            assert row["action_timing"] == "BEFORE"
            assert row["event_manipulation"] == "UPDATE"


# =============================================================================
# Test: Strategy immutability — mutable columns OK, immutable columns blocked
# =============================================================================


@pytest.mark.integration
class TestStrategyImmutability:
    """Verify selective immutability on strategies table."""

    def test_update_mutable_status_succeeds(self, trigger_test_scaffold: dict) -> None:
        """UPDATE of status (mutable) must succeed."""
        sid = trigger_test_scaffold["strategy_id"]
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE strategies SET status = 'testing' WHERE strategy_id = %s "
                "RETURNING strategy_id",
                (sid,),
            )
            assert cur.fetchone() is not None

    def test_update_mutable_activated_at_succeeds(self, trigger_test_scaffold: dict) -> None:
        """UPDATE of activated_at (mutable) must succeed."""
        sid = trigger_test_scaffold["strategy_id"]
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE strategies SET activated_at = NOW() WHERE strategy_id = %s "
                "RETURNING strategy_id",
                (sid,),
            )
            assert cur.fetchone() is not None

    def test_update_mutable_counters_succeeds(self, trigger_test_scaffold: dict) -> None:
        """UPDATE of performance counters (mutable) must succeed."""
        sid = trigger_test_scaffold["strategy_id"]
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE strategies SET paper_trades_count = 5, "
                "paper_roi = %s WHERE strategy_id = %s "
                "RETURNING strategy_id",
                (Decimal("0.1234"), sid),
            )
            assert cur.fetchone() is not None

    def test_update_immutable_config_raises(self, trigger_test_scaffold: dict) -> None:
        """UPDATE of config (immutable) must raise."""
        sid = trigger_test_scaffold["strategy_id"]
        with pytest.raises(psycopg2.errors.RaiseException, match="immutable"):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE strategies SET config = %s WHERE strategy_id = %s",
                    (json.dumps({"param": "tampered"}), sid),
                )

    def test_update_immutable_version_raises(self, trigger_test_scaffold: dict) -> None:
        """UPDATE of strategy_version (immutable) must raise."""
        sid = trigger_test_scaffold["strategy_id"]
        with pytest.raises(psycopg2.errors.RaiseException, match="immutable"):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE strategies SET strategy_version = '2.0' WHERE strategy_id = %s",
                    (sid,),
                )

    def test_update_immutable_name_raises(self, trigger_test_scaffold: dict) -> None:
        """UPDATE of strategy_name (immutable) must raise."""
        sid = trigger_test_scaffold["strategy_id"]
        with pytest.raises(psycopg2.errors.RaiseException, match="immutable"):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE strategies SET strategy_name = 'tampered-name' WHERE strategy_id = %s",
                    (sid,),
                )

    def test_update_immutable_type_raises(self, trigger_test_scaffold: dict) -> None:
        """UPDATE of strategy_type (immutable) must raise.

        Uses a valid FK value ('arbitrage') so the trigger — not the FK
        constraint — is what blocks the change.
        """
        sid = trigger_test_scaffold["strategy_id"]
        with pytest.raises(psycopg2.errors.RaiseException, match="immutable"):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE strategies SET strategy_type = 'arbitrage' WHERE strategy_id = %s",
                    (sid,),
                )

    def test_noop_update_of_immutable_column_succeeds(self, trigger_test_scaffold: dict) -> None:
        """UPDATE that sets an immutable column to its SAME value must succeed.

        IS DISTINCT FROM returns FALSE when old == new, so the trigger
        allows no-op updates. This is important for ORM bulk-save patterns
        that SET all columns even when only one changed.
        """
        sid = trigger_test_scaffold["strategy_id"]
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE strategies SET config = config, status = 'active' "
                "WHERE strategy_id = %s RETURNING strategy_id",
                (sid,),
            )
            assert cur.fetchone() is not None

    def test_update_multiple_immutable_columns_raises(self, trigger_test_scaffold: dict) -> None:
        """UPDATE of multiple immutable columns at once must raise."""
        sid = trigger_test_scaffold["strategy_id"]
        with pytest.raises(psycopg2.errors.RaiseException, match="immutable"):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE strategies SET config = %s, strategy_name = 'x' WHERE strategy_id = %s",
                    (json.dumps({"tampered": True}), sid),
                )

    def test_update_zero_rows_no_exception(self, trigger_test_scaffold: dict) -> None:
        """UPDATE matching zero rows must NOT raise (trigger fires per-row)."""
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE strategies SET config = %s WHERE strategy_id = -999",
                (json.dumps({"tampered": True}),),
            )
            assert cur.rowcount == 0


# =============================================================================
# Test: Model immutability — mutable columns OK, immutable columns blocked
# =============================================================================


@pytest.mark.integration
class TestModelImmutability:
    """Verify selective immutability on probability_models table."""

    def test_update_mutable_status_succeeds(self, trigger_test_scaffold: dict) -> None:
        """UPDATE of status (mutable) must succeed."""
        mid = trigger_test_scaffold["model_id"]
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE probability_models SET status = 'testing' "
                "WHERE model_id = %s RETURNING model_id",
                (mid,),
            )
            assert cur.fetchone() is not None

    def test_update_mutable_validation_succeeds(self, trigger_test_scaffold: dict) -> None:
        """UPDATE of validation_accuracy (mutable) must succeed."""
        mid = trigger_test_scaffold["model_id"]
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE probability_models SET validation_accuracy = %s "
                "WHERE model_id = %s RETURNING model_id",
                (Decimal("0.8765"), mid),
            )
            assert cur.fetchone() is not None

    def test_update_immutable_config_raises(self, trigger_test_scaffold: dict) -> None:
        """UPDATE of config (immutable) must raise."""
        mid = trigger_test_scaffold["model_id"]
        with pytest.raises(psycopg2.errors.RaiseException, match="immutable"):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE probability_models SET config = %s WHERE model_id = %s",
                    (json.dumps({"learning_rate": "0.99"}), mid),
                )

    def test_update_immutable_version_raises(self, trigger_test_scaffold: dict) -> None:
        """UPDATE of model_version (immutable) must raise."""
        mid = trigger_test_scaffold["model_id"]
        with pytest.raises(psycopg2.errors.RaiseException, match="immutable"):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE probability_models SET model_version = '2.0' WHERE model_id = %s",
                    (mid,),
                )

    def test_update_immutable_name_raises(self, trigger_test_scaffold: dict) -> None:
        """UPDATE of model_name (immutable) must raise."""
        mid = trigger_test_scaffold["model_id"]
        with pytest.raises(psycopg2.errors.RaiseException, match="immutable"):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE probability_models SET model_name = 'tampered' WHERE model_id = %s",
                    (mid,),
                )

    def test_update_immutable_class_raises(self, trigger_test_scaffold: dict) -> None:
        """UPDATE of model_class (immutable) must raise.

        Uses a valid FK value ('ensemble') so the trigger — not the FK
        constraint — is what blocks the change.
        """
        mid = trigger_test_scaffold["model_id"]
        with pytest.raises(psycopg2.errors.RaiseException, match="immutable"):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE probability_models SET model_class = 'ensemble' WHERE model_id = %s",
                    (mid,),
                )

    def test_noop_update_of_immutable_column_succeeds(self, trigger_test_scaffold: dict) -> None:
        """No-op UPDATE (same value) must succeed — IS DISTINCT FROM semantics."""
        mid = trigger_test_scaffold["model_id"]
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE probability_models SET config = config, status = 'active' "
                "WHERE model_id = %s RETURNING model_id",
                (mid,),
            )
            assert cur.fetchone() is not None

    def test_update_multiple_immutable_columns_raises(self, trigger_test_scaffold: dict) -> None:
        """UPDATE of multiple immutable columns at once must raise."""
        mid = trigger_test_scaffold["model_id"]
        with pytest.raises(psycopg2.errors.RaiseException, match="immutable"):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE probability_models SET config = %s, model_name = 'x' "
                    "WHERE model_id = %s",
                    (json.dumps({"tampered": True}), mid),
                )

    def test_update_zero_rows_no_exception(self, trigger_test_scaffold: dict) -> None:
        """UPDATE matching zero rows must NOT raise (trigger fires per-row)."""
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE probability_models SET config = %s WHERE model_id = -999",
                (json.dumps({"tampered": True}),),
            )
            assert cur.rowcount == 0


# =============================================================================
# Test: Append-only enforcement — INSERT OK, UPDATE blocked
# =============================================================================


def _insert_append_only_row(
    cur: Any,
    table: str,
    scaffold: dict,
) -> int:
    """INSERT a minimal valid row into an append-only table. Returns PK."""
    pid = scaffold["platform_id"]
    pos_id = scaffold["position_internal_id"]
    mkt_id = scaffold["market_id"]

    if table == "trades":
        cur.execute(
            """
            INSERT INTO trades (
                platform_id, market_id, side, price,
                quantity, execution_environment
            )
            VALUES (%s, %s, 'buy', %s, 1, 'live')
            RETURNING id
            """,
            (pid, mkt_id, Decimal("0.5000")),
        )
        return cur.fetchone()["id"]

    if table == "settlements":
        cur.execute(
            """
            INSERT INTO settlements (
                platform_id, market_id, outcome, payout,
                execution_environment
            )
            VALUES (%s, %s, 'yes', %s, 'live')
            RETURNING id
            """,
            (pid, mkt_id, Decimal("1.0000")),
        )
        return cur.fetchone()["id"]

    if table == "account_ledger":
        cur.execute(
            """
            INSERT INTO account_ledger (
                platform_id, transaction_type, amount,
                running_balance, execution_environment
            )
            VALUES (%s, 'deposit', %s, %s, 'live')
            RETURNING id
            """,
            (pid, Decimal("100.0000"), Decimal("100.0000")),
        )
        return cur.fetchone()["id"]

    if table == "position_exits":
        cur.execute(
            """
            INSERT INTO position_exits (
                position_internal_id, exit_reason, execution_environment
            )
            VALUES (%s, 'test_trigger', 'live')
            RETURNING exit_id
            """,
            (pos_id,),
        )
        return cur.fetchone()["exit_id"]

    if table == "exit_attempts":
        cur.execute(
            """
            INSERT INTO exit_attempts (
                position_internal_id, exit_reason, execution_environment
            )
            VALUES (%s, 'test_trigger', 'live')
            RETURNING attempt_id
            """,
            (pos_id,),
        )
        return cur.fetchone()["attempt_id"]

    raise ValueError(f"Unknown table: {table}")


# PK column name per table (for the UPDATE WHERE clause).
_PK_COLUMN = {
    "trades": "id",
    "settlements": "id",
    "account_ledger": "id",
    "position_exits": "exit_id",
    "exit_attempts": "attempt_id",
}

# A harmless column to attempt UPDATE on (exists on all 5 tables).
_UPDATE_COLUMN = {
    "trades": "price",
    "settlements": "payout",
    "account_ledger": "amount",
    "position_exits": "exit_reason",
    "exit_attempts": "exit_reason",
}

_UPDATE_VALUE = {
    "trades": Decimal("0.9999"),
    "settlements": Decimal("0.0001"),
    "account_ledger": Decimal("999.0000"),
    "position_exits": "tampered",
    "exit_attempts": "tampered",
}


@pytest.mark.integration
class TestAppendOnlyEnforcement:
    """Verify INSERT succeeds and UPDATE is blocked on all 5 append-only tables."""

    @pytest.mark.parametrize("table", APPEND_ONLY_TABLES)
    def test_insert_succeeds(self, trigger_test_scaffold: dict, table: str) -> None:
        """INSERT into append-only table must succeed normally."""
        with get_cursor(commit=True) as cur:
            pk = _insert_append_only_row(cur, table, trigger_test_scaffold)
            assert pk is not None

    @pytest.mark.parametrize("table", APPEND_ONLY_TABLES)
    def test_update_raises(self, trigger_test_scaffold: dict, table: str) -> None:
        """UPDATE on append-only table must raise with clear message."""
        with get_cursor(commit=True) as cur:
            pk = _insert_append_only_row(cur, table, trigger_test_scaffold)

        pk_col = _PK_COLUMN[table]
        upd_col = _UPDATE_COLUMN[table]
        upd_val = _UPDATE_VALUE[table]
        with pytest.raises(psycopg2.errors.RaiseException, match="append-only"):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    f"UPDATE {table} SET {upd_col} = %s WHERE {pk_col} = %s",  # noqa: S608
                    (upd_val, pk),
                )

    @pytest.mark.parametrize("table", APPEND_ONLY_TABLES)
    def test_delete_still_works(self, trigger_test_scaffold: dict, table: str) -> None:
        """DELETE must still work — triggers only block UPDATE, not DELETE.

        This confirms cleanup and administrative corrections remain possible.
        """
        with get_cursor(commit=True) as cur:
            pk = _insert_append_only_row(cur, table, trigger_test_scaffold)

        with get_cursor(commit=True) as cur:
            pk_col = _PK_COLUMN[table]
            cur.execute(
                f"DELETE FROM {table} WHERE {pk_col} = %s RETURNING {pk_col}",  # noqa: S608
                (pk,),
            )
            assert cur.fetchone() is not None
