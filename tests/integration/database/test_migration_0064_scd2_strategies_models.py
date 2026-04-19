"""Integration tests for migration 0064 -- C2c SCD2 on strategies + probability_models.

Verifies the POST-MIGRATION state of ``row_current_ind``, ``row_start_ts``,
``row_end_ts`` on ``strategies`` and ``probability_models``, plus the
SCD2 supersede contracts that keep those columns consistent across
status transitions and the ``create_model`` INSERT-with-SCD2-columns path.

Test groups:
    - TestSCD2ColumnsPresent: the three temporal columns exist with the
      correct types, nullability, and DEFAULTs on each of the two tables.
    - TestPartialUniqueIndexes: partial UNIQUE on ``(name, version)
      WHERE row_current_ind = TRUE`` exists on both tables and the
      full UNIQUEs (``unique_strategy_name_version``,
      ``unique_model_name_version``) are GONE.
    - TestUpdateStrategyStatusSupersedes: ``update_strategy_status``
      closes the old row (row_current_ind=FALSE, row_end_ts set) and
      inserts a new row with the new status and matching
      ``(strategy_name, strategy_version)``.
    - TestCreateModelWritesSCD2Columns: ``ModelManager.create_model``
      persists ``row_current_ind=TRUE``, ``row_end_ts=NULL``, and a
      non-NULL ``row_start_ts``.
    - TestModelSupersedeManualFlow: manually executed close+INSERT on
      ``probability_models`` honours the partial UNIQUE: current row
      uniqueness enforced, historical row collision permitted.
    - TestPartialUniqueEnforcement: attempting to INSERT a second
      CURRENT row with a colliding ``(name, version)`` raises
      UniqueViolation; inserting a HISTORICAL row with a colliding
      ``(name, version)`` succeeds.

Issue: #791
Epic: #745 (Schema Hardening Arc, Cohort C2c)

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

from precog.analytics.model_manager import ModelManager
from precog.database.connection import get_cursor
from precog.database.crud_strategies import (
    create_strategy,
    get_strategy,
    update_strategy_status,
)

pytestmark = [pytest.mark.integration]


# =============================================================================
# Per-table spec (mirrors migration 0064 ``_SCD2_SPEC``)
# =============================================================================

# (table, partial_idx_name, natural_key_cols_text, dropped_full_uq_name)
_SCD2_SPEC: list[tuple[str, str, str, str]] = [
    (
        "strategies",
        "idx_strategies_name_version_current",
        "strategy_name, strategy_version",
        "unique_strategy_name_version",
    ),
    (
        "probability_models",
        "idx_probability_models_name_version_current",
        "model_name, model_version",
        "unique_model_name_version",
    ),
]


# =============================================================================
# Group 1: SCD2 columns present with correct shape
# =============================================================================


@pytest.mark.parametrize(
    ("table", "_idx", "_cols", "_dropped"),
    _SCD2_SPEC,
)
def test_row_current_ind_column_shape(
    db_pool: Any, table: str, _idx: str, _cols: str, _dropped: str
) -> None:
    """``row_current_ind`` exists, is BOOLEAN NOT NULL with DEFAULT TRUE."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = 'row_current_ind'
            """,
            (table,),
        )
        row = cur.fetchone()
    assert row is not None, f"{table}.row_current_ind missing post-0064"
    assert row["data_type"] == "boolean", f"{table}.row_current_ind wrong type: {row['data_type']}"
    assert row["is_nullable"] == "NO", f"{table}.row_current_ind must be NOT NULL"
    default = row["column_default"]
    assert default is not None, f"{table}.row_current_ind must have a default"
    assert "true" in default.lower(), (
        f"{table}.row_current_ind must default to TRUE; got {default!r}"
    )


@pytest.mark.parametrize(
    ("table", "_idx", "_cols", "_dropped"),
    _SCD2_SPEC,
)
def test_row_start_ts_column_shape(
    db_pool: Any, table: str, _idx: str, _cols: str, _dropped: str
) -> None:
    """``row_start_ts`` exists, is TIMESTAMPTZ NOT NULL with DEFAULT NOW()."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = 'row_start_ts'
            """,
            (table,),
        )
        row = cur.fetchone()
    assert row is not None, f"{table}.row_start_ts missing post-0064"
    assert row["data_type"] == "timestamp with time zone", (
        f"{table}.row_start_ts wrong type: {row['data_type']}"
    )
    assert row["is_nullable"] == "NO", f"{table}.row_start_ts must be NOT NULL"
    default = row["column_default"]
    assert default is not None, f"{table}.row_start_ts must have a default"
    assert "now()" in default.lower(), (
        f"{table}.row_start_ts must default to NOW(); got {default!r}"
    )


@pytest.mark.parametrize(
    ("table", "_idx", "_cols", "_dropped"),
    _SCD2_SPEC,
)
def test_row_end_ts_column_shape(
    db_pool: Any, table: str, _idx: str, _cols: str, _dropped: str
) -> None:
    """``row_end_ts`` exists, is TIMESTAMPTZ NULL with no default."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = 'row_end_ts'
            """,
            (table,),
        )
        row = cur.fetchone()
    assert row is not None, f"{table}.row_end_ts missing post-0064"
    assert row["data_type"] == "timestamp with time zone", (
        f"{table}.row_end_ts wrong type: {row['data_type']}"
    )
    assert row["is_nullable"] == "YES", f"{table}.row_end_ts must be NULLABLE"


# =============================================================================
# Group 2: Partial UNIQUE indexes replace the full UNIQUEs
# =============================================================================


@pytest.mark.parametrize(
    ("table", "partial_idx", "cols", "dropped_uq"),
    _SCD2_SPEC,
)
def test_partial_unique_index_exists(
    db_pool: Any, table: str, partial_idx: str, cols: str, dropped_uq: str
) -> None:
    """Partial UNIQUE WHERE row_current_ind = TRUE exists on (name, version)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexdef FROM pg_indexes
            WHERE tablename = %s AND indexname = %s
            """,
            (table, partial_idx),
        )
        row = cur.fetchone()
    assert row is not None, f"{table}.{partial_idx} missing post-0064"
    indexdef = row["indexdef"]
    assert "UNIQUE" in indexdef, f"{partial_idx} must be UNIQUE"
    assert "row_current_ind = true" in indexdef, (
        f"{partial_idx} must filter on row_current_ind = TRUE; got: {indexdef}"
    )


@pytest.mark.parametrize(
    ("table", "_idx", "_cols", "dropped_uq"),
    _SCD2_SPEC,
)
def test_full_unique_constraint_dropped(
    db_pool: Any, table: str, _idx: str, _cols: str, dropped_uq: str
) -> None:
    """The pre-0064 unconditional UNIQUE constraint is gone."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = %s AND constraint_name = %s
            """,
            (table, dropped_uq),
        )
        row = cur.fetchone()
    assert row is None, (
        f"{table} still has the pre-0064 UNIQUE {dropped_uq!r} — "
        f"SCD2 supersede is blocked until it is dropped"
    )


# =============================================================================
# Group 3: update_strategy_status SCD2 supersede
# =============================================================================


def test_update_strategy_status_supersedes_current_row(db_pool: Any) -> None:
    """SCD2 contract: close old row + INSERT new row with same (name, version).

    This is the load-bearing test for migration 0064 on the strategies
    side.  After ``update_strategy_status``:
        * exactly one row has ``row_current_ind = TRUE`` for the natural key
        * the closed row has ``row_end_ts`` set and ``row_current_ind = FALSE``
        * both rows share the same ``(strategy_name, strategy_version)``
        * the new row has a new ``strategy_id``
        * the new row has the new ``status``
    """
    # Unique natural key for this test — UUID-based so re-runs are safe.
    suffix = uuid.uuid4().hex[:8]
    strategy_name = f"test_0064_supersede_{suffix}"
    strategy_version = "v1.0"

    # Clean slate: remove any residue from a prior failed run.
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM strategies WHERE strategy_name = %s",
            (strategy_name,),
        )

    try:
        # Create a draft strategy.
        first_id = create_strategy(
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            strategy_type="momentum",
            config={"min_lead": 7, "kelly_fraction": Decimal("0.25")},
            status="draft",
        )
        assert first_id is not None

        # Confirm the starting state is one current row.
        with get_cursor() as cur:
            cur.execute(
                "SELECT strategy_id, status, row_current_ind, row_end_ts "
                "FROM strategies WHERE strategy_name = %s ORDER BY strategy_id",
                (strategy_name,),
            )
            pre_rows = cur.fetchall()
        assert len(pre_rows) == 1, f"Expected 1 pre-supersede row; got {len(pre_rows)}"
        assert pre_rows[0]["row_current_ind"] is True
        assert pre_rows[0]["row_end_ts"] is None
        assert pre_rows[0]["status"] == "draft"

        # Supersede: draft -> testing.
        ok = update_strategy_status(strategy_id=first_id, new_status="testing")
        assert ok is True, "update_strategy_status must return True on supersede"

        # Post-supersede state: 2 rows, 1 closed + 1 current.
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT strategy_id, strategy_name, strategy_version, status,
                       row_current_ind, row_end_ts
                FROM strategies
                WHERE strategy_name = %s
                ORDER BY strategy_id
                """,
                (strategy_name,),
            )
            rows = cur.fetchall()
        assert len(rows) == 2, f"Expected 2 SCD rows post-supersede; got {len(rows)}"

        closed = next(r for r in rows if r["strategy_id"] == first_id)
        current = next(r for r in rows if r["strategy_id"] != first_id)

        assert closed["row_current_ind"] is False
        assert closed["row_end_ts"] is not None, "Closed row must have row_end_ts"
        assert closed["status"] == "draft", "Closed row preserves original status"

        assert current["row_current_ind"] is True
        assert current["row_end_ts"] is None
        assert current["status"] == "testing"

        # Natural key (strategy_name, strategy_version) preserved across versions.
        assert closed["strategy_name"] == current["strategy_name"] == strategy_name
        assert closed["strategy_version"] == current["strategy_version"] == strategy_version
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM strategies WHERE strategy_name = %s",
                (strategy_name,),
            )


def test_update_strategy_status_returns_false_for_historical_row(
    db_pool: Any,
) -> None:
    """Superseding a historical (already closed) strategy_id returns False.

    Contract: ``update_strategy_status`` only supersedes CURRENT rows.
    If the caller holds a stale id from before a prior supersede, the
    call must no-op (return False) rather than creating a fork in the
    version chain.
    """
    suffix = uuid.uuid4().hex[:8]
    strategy_name = f"test_0064_historical_{suffix}"

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM strategies WHERE strategy_name = %s",
            (strategy_name,),
        )

    try:
        first_id = create_strategy(
            strategy_name=strategy_name,
            strategy_version="v1.0",
            strategy_type="value",
            config={"k": "v"},
            status="draft",
        )
        assert first_id is not None

        # First supersede: closes ``first_id``, creates a new row.
        assert update_strategy_status(first_id, "testing") is True

        # Second supersede against the CLOSED id: must return False.
        ok = update_strategy_status(first_id, "active")
        assert ok is False, (
            "update_strategy_status on a historical id must return False (no fork in the SCD chain)"
        )

        # Row graph stayed at exactly 2 rows (no fork).
        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS c FROM strategies WHERE strategy_name = %s",
                (strategy_name,),
            )
            total = int(cur.fetchone()["c"])
        assert total == 2, f"Expected 2 rows, got {total} (fork detected)"
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM strategies WHERE strategy_name = %s",
                (strategy_name,),
            )


def test_update_strategy_status_preserves_config_immutability(db_pool: Any) -> None:
    """Supersede carries config forward verbatim — the trigger does not fire.

    The ``trg_strategies_immutability`` trigger guards
    ``config, strategy_version, strategy_name, strategy_type`` on
    UPDATE.  The CLOSE-UPDATE in ``update_strategy_status`` touches only
    ``row_current_ind`` + ``row_end_ts``, so the trigger's IS DISTINCT
    FROM checks pass.  This test acts as a regression guard: if a
    future edit to supersede accidentally SETs one of the guarded
    columns, this test fails loudly.
    """
    suffix = uuid.uuid4().hex[:8]
    strategy_name = f"test_0064_immut_{suffix}"
    original_config = {"min_edge": "0.05", "kelly_fraction": "0.25"}

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM strategies WHERE strategy_name = %s",
            (strategy_name,),
        )

    try:
        first_id = create_strategy(
            strategy_name=strategy_name,
            strategy_version="v1.0",
            strategy_type="momentum",
            config=original_config,
            status="draft",
        )
        assert first_id is not None

        # Trigger would RAISE on any UPDATE of config — so this call
        # succeeding is itself evidence that supersede does NOT touch
        # guarded columns.
        assert update_strategy_status(first_id, "testing") is True

        # Re-resolve the CURRENT row via the natural key (post-0064
        # supersede allocates a new strategy_id; get_strategy filters to
        # row_current_ind = TRUE and the old id is now historical).
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM strategies
                WHERE strategy_name = %s AND row_current_ind = TRUE
                """,
                (strategy_name,),
            )
            current_row = cur.fetchone()
        assert current_row is not None, "Post-supersede current row missing"
        # config stored verbatim on the CURRENT row.  Parse through
        # ``_convert_config_strings_to_decimal`` so we compare
        # Decimal values (not raw JSONB strings) — restores the
        # semantic value-equality that the pre-0064 test enforced
        # but the post-0064 "key-set only" variant silently
        # weakened.  Glokta P1-2.
        from precog.database.crud_shared import _convert_config_strings_to_decimal

        stored_config = current_row["config"]
        if isinstance(stored_config, str):
            stored_config = json.loads(stored_config)
        stored_decoded = _convert_config_strings_to_decimal(stored_config)
        original_decoded = _convert_config_strings_to_decimal(original_config)
        assert stored_decoded == original_decoded, (
            f"Config values must be preserved verbatim across supersede. "
            f"stored={stored_decoded!r}, original={original_decoded!r}"
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM strategies WHERE strategy_name = %s",
                (strategy_name,),
            )


# =============================================================================
# Group 4: create_model writes explicit SCD2 columns
# =============================================================================


def test_create_model_writes_scd2_columns(db_pool: Any) -> None:
    """``create_model`` persists SCD2 columns with correct initial values."""
    suffix = uuid.uuid4().hex[:8]
    model_name = f"test_0064_create_{suffix}"
    model_version = "v1.0"

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM probability_models WHERE model_name = %s",
            (model_name,),
        )

    try:
        manager = ModelManager()
        model = manager.create_model(
            model_name=model_name,
            model_version=model_version,
            model_class="elo",
            config={"k_factor": Decimal("32.0")},
            domain="nfl",
        )
        model_id = model["model_id"]

        with get_cursor() as cur:
            cur.execute(
                """
                SELECT row_current_ind, row_start_ts, row_end_ts
                FROM probability_models WHERE model_id = %s
                """,
                (model_id,),
            )
            row = cur.fetchone()
        assert row is not None
        assert row["row_current_ind"] is True, "create_model must set row_current_ind = TRUE"
        assert row["row_end_ts"] is None, (
            "create_model must set row_end_ts = NULL for a current row"
        )
        assert row["row_start_ts"] is not None, "create_model must populate row_start_ts"
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM probability_models WHERE model_name = %s",
                (model_name,),
            )


# =============================================================================
# Group 5: Partial UNIQUE enforces exactly one CURRENT row per (name, version)
# =============================================================================


def test_strategies_partial_unique_allows_historical_collisions(
    db_pool: Any,
) -> None:
    """Partial UNIQUE on strategies permits historical (name, version) collisions.

    Two rows may share ``(strategy_name, strategy_version)`` as long as
    at most ONE has ``row_current_ind = TRUE``.  A real supersede
    produces exactly this state.
    """
    suffix = uuid.uuid4().hex[:8]
    strategy_name = f"test_0064_partial_ok_{suffix}"

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM strategies WHERE strategy_name = %s",
            (strategy_name,),
        )
    try:
        first_id = create_strategy(
            strategy_name=strategy_name,
            strategy_version="v1.0",
            strategy_type="momentum",
            config={"a": 1},
            status="draft",
        )
        assert first_id is not None
        assert update_strategy_status(first_id, "testing") is True

        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN row_current_ind THEN 1 ELSE 0 END) AS current_count "
                "FROM strategies WHERE strategy_name = %s",
                (strategy_name,),
            )
            row = cur.fetchone()
        assert int(row["total"]) == 2, "SCD supersede should have produced 2 rows"
        assert int(row["current_count"]) == 1, (
            "Partial UNIQUE must allow exactly one current row per (name, version)"
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM strategies WHERE strategy_name = %s",
                (strategy_name,),
            )


def test_strategies_partial_unique_rejects_duplicate_current_rows(
    db_pool: Any,
) -> None:
    """A second CURRENT row with a colliding (name, version) raises UniqueViolation.

    Direct INSERT of a second current row with the same natural key must
    be rejected by the partial UNIQUE — this is the load-bearing
    correctness invariant that protects supersede from double-write
    races.
    """
    suffix = uuid.uuid4().hex[:8]
    strategy_name = f"test_0064_partial_reject_{suffix}"

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM strategies WHERE strategy_name = %s",
            (strategy_name,),
        )

    try:
        # Seed one current row.
        first_id = create_strategy(
            strategy_name=strategy_name,
            strategy_version="v1.0",
            strategy_type="momentum",
            config={"a": 1},
            status="draft",
        )
        assert first_id is not None

        # Attempt to insert a SECOND current row with the same
        # (name, version) — must fail on the partial UNIQUE.
        with pytest.raises(psycopg2.errors.UniqueViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO strategies (
                        strategy_name, strategy_version, strategy_type, config,
                        status, row_current_ind, row_start_ts, row_end_ts
                    )
                    VALUES (%s, %s, %s, %s::jsonb, %s, TRUE, NOW(), NULL)
                    """,
                    (
                        strategy_name,
                        "v1.0",
                        "value",
                        json.dumps({"b": 2}),
                        "draft",
                    ),
                )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM strategies WHERE strategy_name = %s",
                (strategy_name,),
            )


def test_probability_models_partial_unique_allows_historical_collisions(
    db_pool: Any,
) -> None:
    """Manual close+INSERT on probability_models honours the partial UNIQUE.

    Exercises the same SCD2 invariant as the strategies supersede
    test, but for probability_models via a manual close-and-insert
    (since ``ModelManager`` does not yet implement SCD supersede — the
    spec only requires ``create_model`` to populate SCD2 columns on
    first INSERT).  This gives us coverage of the partial-UNIQUE
    behaviour on the models side without requiring a CRUD change.
    """
    suffix = uuid.uuid4().hex[:8]
    model_name = f"test_0064_pmodel_scd_{suffix}"

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM probability_models WHERE model_name = %s",
            (model_name,),
        )

    try:
        manager = ModelManager()
        # First (current) row.
        manager.create_model(
            model_name=model_name,
            model_version="v1.0",
            model_class="elo",
            config={"k_factor": Decimal("32.0")},
            domain="nfl",
        )

        # Manual supersede: close the current row, insert a new current row.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                UPDATE probability_models
                SET row_current_ind = FALSE,
                    row_end_ts = NOW()
                WHERE model_name = %s AND row_current_ind = TRUE
                """,
                (model_name,),
            )
            cur.execute(
                """
                INSERT INTO probability_models (
                    model_name, model_version, model_class, domain, config,
                    status, row_current_ind, row_start_ts, row_end_ts
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s,
                        TRUE, NOW(), NULL)
                """,
                (
                    model_name,
                    "v1.0",
                    "elo",
                    "nfl",
                    json.dumps({"k_factor": "32.0"}),
                    "draft",
                ),
            )

        # Should have 2 rows total, exactly 1 current.
        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN row_current_ind THEN 1 ELSE 0 END) AS current_count "
                "FROM probability_models WHERE model_name = %s",
                (model_name,),
            )
            row = cur.fetchone()
        assert int(row["total"]) == 2
        assert int(row["current_count"]) == 1
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM probability_models WHERE model_name = %s",
                (model_name,),
            )


def test_probability_models_partial_unique_rejects_duplicate_current_rows(
    db_pool: Any,
) -> None:
    """A second current (model_name, model_version) row raises UniqueViolation."""
    suffix = uuid.uuid4().hex[:8]
    model_name = f"test_0064_pmodel_reject_{suffix}"

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM probability_models WHERE model_name = %s",
            (model_name,),
        )

    try:
        manager = ModelManager()
        manager.create_model(
            model_name=model_name,
            model_version="v1.0",
            model_class="elo",
            config={"k_factor": Decimal("32.0")},
            domain="nfl",
        )

        with pytest.raises(psycopg2.errors.UniqueViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO probability_models (
                        model_name, model_version, model_class, domain, config,
                        status, row_current_ind, row_start_ts, row_end_ts
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s,
                            TRUE, NOW(), NULL)
                    """,
                    (
                        model_name,
                        "v1.0",
                        "elo",
                        "nfl",
                        json.dumps({"k_factor": "99.0"}),
                        "draft",
                    ),
                )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM probability_models WHERE model_name = %s",
                (model_name,),
            )


# =============================================================================
# Group 7: Read CRUDs filter row_current_ind = TRUE (Glokta P0-3 / Ripley #NEW-C)
# =============================================================================


def test_get_strategy_excludes_historical_row(db_pool: Any) -> None:
    """``get_strategy(id)`` returns None for a historical (superseded) id.

    Post-Migration 0064, the read CRUDs must filter ``row_current_ind =
    TRUE``.  Before the remediation, ``get_strategy(closed_id)`` returned
    the stale historical row — callers silently saw pre-supersede
    status/metrics.
    """
    from precog.database.crud_strategies import (
        get_active_strategy_version,
        get_all_strategy_versions,
        get_strategy_by_name_and_version,
        list_strategies,
    )

    suffix = uuid.uuid4().hex[:8]
    strategy_name = f"test_0064_read_filter_{suffix}"

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM strategies WHERE strategy_name = %s",
            (strategy_name,),
        )

    try:
        first_id = create_strategy(
            strategy_name=strategy_name,
            strategy_version="v1.0",
            strategy_type="momentum",
            config={"min_lead": 7},
            status="draft",
        )
        assert first_id is not None

        # Supersede: closes first_id, creates a new current row.
        assert update_strategy_status(first_id, "active") is True

        # get_strategy on the CLOSED id returns None (no current row).
        assert get_strategy(first_id) is None, (
            "get_strategy must return None for a superseded id (row_current_ind = FALSE)"
        )

        # get_strategy_by_name_and_version returns the CURRENT row.
        current = get_strategy_by_name_and_version(strategy_name, "v1.0")
        assert current is not None, "Natural-key lookup must find the current row"
        assert current["status"] == "active", (
            f"Natural-key lookup must return the current row (not the closed historical). "
            f"Got status={current['status']!r}"
        )
        assert current["strategy_id"] != first_id, "Current row must have the NEW SCD id"

        # get_active_strategy_version must not shadow with the closed row.
        active = get_active_strategy_version(strategy_name)
        assert active is not None
        assert active["strategy_id"] == current["strategy_id"], (
            f"get_active_strategy_version returned the wrong row. "
            f"Got strategy_id={active['strategy_id']}, expected {current['strategy_id']}"
        )

        # get_all_strategy_versions default: only current rows (1 row).
        versions = get_all_strategy_versions(strategy_name)
        assert len(versions) == 1, (
            f"Default get_all_strategy_versions must return only current rows; got {len(versions)}"
        )
        assert versions[0]["strategy_id"] == current["strategy_id"]

        # With include_historical=True: both the closed + current (2 rows).
        all_versions = get_all_strategy_versions(strategy_name, include_historical=True)
        assert len(all_versions) == 2, (
            f"include_historical=True must surface the closed row too; got {len(all_versions)}"
        )

        # list_strategies filtered by name: only 1 current row regardless of status filter.
        all_active = list_strategies(status="active", limit=100)
        live = [s for s in all_active if s["strategy_name"] == strategy_name]
        assert len(live) == 1, (
            f"list_strategies(status='active') must return only the CURRENT active row; got {len(live)}"
        )
        assert live[0]["strategy_id"] == current["strategy_id"]
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM strategies WHERE strategy_name = %s",
                (strategy_name,),
            )


def test_model_manager_get_model_excludes_historical_row(db_pool: Any) -> None:
    """``ModelManager.get_model(id)`` returns None for a superseded id."""
    suffix = uuid.uuid4().hex[:8]
    model_name = f"test_0064_read_filter_{suffix}"

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM probability_models WHERE model_name = %s",
            (model_name,),
        )

    try:
        manager = ModelManager()
        created = manager.create_model(
            model_name=model_name,
            model_version="v1.0",
            model_class="elo",
            config={"k_factor": Decimal("32.0")},
            domain="nfl",
        )
        first_id = created["model_id"]

        # Supersede via the manager-level path (draft -> testing).
        superseded = manager.update_status(first_id, "testing")
        assert superseded["model_id"] != first_id, (
            "update_status supersede must allocate a new model_id"
        )

        # get_model by the CLOSED id returns None (row_current_ind filter).
        assert manager.get_model(model_id=first_id) is None, (
            "get_model on a superseded id must return None"
        )

        # get_model via natural key returns the current row.
        current = manager.get_model(model_name=model_name, model_version="v1.0")
        assert current is not None
        assert current["status"] == "testing"
        assert current["model_id"] == superseded["model_id"]

        # get_models_by_name returns ONE row per logical version.
        all_versions = manager.get_models_by_name(model_name)
        assert len(all_versions) == 1, (
            f"get_models_by_name must return one row per logical version; got {len(all_versions)}"
        )

        # list_models returns the current row only.
        active_models = manager.list_models(status="testing")
        live = [m for m in active_models if m["model_name"] == model_name]
        assert len(live) == 1
        assert live[0]["model_id"] == superseded["model_id"]
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM probability_models WHERE model_name = %s",
                (model_name,),
            )


def test_update_strategy_status_carries_forward_activated_at(db_pool: Any) -> None:
    """P1-1 integration: activated_at carries forward on a deactivate call.

    Scenario (from Glokta P1-1):
        1. Create strategy, status=draft.
        2. Activate at t1 (activated_at=t1, deactivated_at=None).
        3. Deactivate at t2 (caller passes deactivated_at=t2, NO activated_at).
        4. Post-remediation: current row has activated_at=t1 AND deactivated_at=t2.

    Pre-remediation bug: step 3 produced activated_at=NULL, deactivated_at=t2 —
    audit chain broken.
    """
    from datetime import UTC, datetime, timedelta

    from precog.database.crud_strategies import update_strategy_status

    suffix = uuid.uuid4().hex[:8]
    strategy_name = f"test_0064_timestamp_carry_{suffix}"

    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM strategies WHERE strategy_name = %s",
            (strategy_name,),
        )

    try:
        first_id = create_strategy(
            strategy_name=strategy_name,
            strategy_version="v1.0",
            strategy_type="momentum",
            config={"min_lead": 7},
            status="draft",
        )
        assert first_id is not None

        # Step 2: activate at t1.  Re-resolve the CURRENT id after each
        # supersede — supersede allocates a new strategy_id each time.
        t1 = datetime(2026, 4, 18, 10, 0, 0, tzinfo=UTC)
        assert update_strategy_status(first_id, "active", activated_at=t1) is True

        with get_cursor() as cur:
            cur.execute(
                """
                SELECT strategy_id, activated_at, deactivated_at, status
                FROM strategies
                WHERE strategy_name = %s AND row_current_ind = TRUE
                """,
                (strategy_name,),
            )
            after_activate = cur.fetchone()
        assert after_activate["activated_at"] == t1
        assert after_activate["deactivated_at"] is None
        assert after_activate["status"] == "active"
        active_id = after_activate["strategy_id"]

        # Step 3: deactivate at t2.  Caller passes ONLY deactivated_at.
        t2 = t1 + timedelta(hours=3)
        assert update_strategy_status(active_id, "deprecated", deactivated_at=t2) is True

        # Step 4: activated_at MUST still be t1 (carry-forward).  This is
        # the regression-guard assertion for Glokta P1-1.
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT activated_at, deactivated_at, status
                FROM strategies
                WHERE strategy_name = %s AND row_current_ind = TRUE
                """,
                (strategy_name,),
            )
            after_deactivate = cur.fetchone()
        assert after_deactivate["activated_at"] == t1, (
            f"P1-1 regression: activated_at must carry forward from the activate call. "
            f"Got {after_deactivate['activated_at']!r}, expected {t1!r}"
        )
        assert after_deactivate["deactivated_at"] == t2
        assert after_deactivate["status"] == "deprecated"
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM strategies WHERE strategy_name = %s",
                (strategy_name,),
            )
