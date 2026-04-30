"""Integration tests for Migration 0076 -- generic ``set_updated_at()`` retrofit.

Verifies the POST-MIGRATION state of the canonical-tier BEFORE UPDATE trigger
infrastructure introduced by Migration 0076 (ADR-118 V2.42 sub-amendment A,
issue #1074).  Migration 0076 ships:

    1. Generic ``set_updated_at()`` PL/pgSQL function (Pattern 73 SSOT).
    2. ``trg_canonical_events_updated_at`` trigger (NEW; closes the
       Migration 0067 orphan-trigger gap).
    3. Rewires ``trg_canonical_markets_updated_at`` /
       ``trg_canonical_market_links_updated_at`` /
       ``trg_canonical_event_links_updated_at`` to the generic function.
    4. DROPs the 3 per-table maintenance functions
       (``update_canonical_markets_updated_at()``,
       ``update_canonical_market_links_updated_at()``,
       ``update_canonical_event_links_updated_at()``).

Test groups (Miles M-5 -- per-table-trigger integration tests REQUIRED):
    - TestGenericFunctionExists: ``set_updated_at()`` exists in pg_proc and
      has the canonical body shape.
    - TestPerTableFunctionsDropped: the 3 per-table maintenance functions
      are gone post-Migration-0076.
    - TestTriggerInstancesPointAtGeneric: 4 triggers across 4 tables all
      EXECUTE FUNCTION ``set_updated_at()``.
    - TestBehavioralFireOnUpdate: INSERT then UPDATE without explicit
      ``updated_at`` and assert the column advanced -- run on all 4
      retrofitted tables.  This is operationally non-negotiable per Miles M-5
      (catches the "generic function broke for all 4 tables" failure mode
      within seconds).
    - TestCanonicalEventsTriggerCoversGap: end-to-end behavioral evidence
      that the orphan-trigger gap from Migration 0067 is closed (UPDATE
      with no explicit ``updated_at`` advances ``updated_at``).

Issues: #1074 (V2.42 sub-amendment A retrofit)
ADR: ADR-118 V2.42 sub-amendment A (generic set_updated_at function +
    4-table retrofit)
Council: ``memory/design_review_0076_synthesis.md`` (Holden + Galadriel +
    Miles + Uhura, session 83)

Markers:
    @pytest.mark.integration: real DB required.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest

from precog.database.connection import get_cursor
from tests.integration.database._canonical_event_helpers import (
    _cleanup_canonical_event,
    _seed_canonical_event,
)
from tests.integration.database._canonical_market_helpers import (
    _cleanup_canonical_market,
    _cleanup_platform_market,
    _get_manual_v1_algorithm_id,
    _seed_canonical_market,
    _seed_platform_market,
)
from tests.integration.database.test_migration_0072_canonical_link_tables import (
    _cleanup_platform_event,
    _seed_platform_event,
)

pytestmark = [pytest.mark.integration]


# Tables retrofitted in Migration 0076.  Pattern 73 SSOT for the test list;
# the migration docstring + the migration code's ``_RETROFIT_TABLES_*`` tuples
# also enumerate this list -- drift would surface as a behavioral test failure.
_RETROFIT_TABLES: tuple[str, ...] = (
    "canonical_events",
    "canonical_markets",
    "canonical_market_links",
    "canonical_event_links",
)


# =============================================================================
# Group 1: Generic function existence + shape
# =============================================================================


def test_set_updated_at_function_exists(db_pool: Any) -> None:
    """``set_updated_at()`` exists in pg_proc post-Migration-0076."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_functiondef(p.oid) AS def
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE p.proname = 'set_updated_at'
              AND n.nspname = 'public'
            """
        )
        row = cur.fetchone()
    assert row is not None, "set_updated_at() must exist post-Migration-0076"
    function_def = row["def"]
    # Body verbatim per Migration 0076 step 1.
    assert "NEW.updated_at = now()" in function_def, (
        f"Function body must set NEW.updated_at = now(); got: {function_def!r}"
    )
    assert "RETURN NEW" in function_def, f"Function body must RETURN NEW; got: {function_def!r}"


def test_set_updated_at_function_has_comment(db_pool: Any) -> None:
    """``set_updated_at()`` has a COMMENT documenting the semantic shift (Uhura-1)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT obj_description(p.oid, 'pg_proc') AS comment
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE p.proname = 'set_updated_at'
              AND n.nspname = 'public'
            """
        )
        row = cur.fetchone()
    assert row is not None, "set_updated_at() must exist"
    comment = row["comment"]
    assert comment is not None, (
        "set_updated_at() must carry a COMMENT (Uhura-1 semantic shift docstring)"
    )
    assert len(comment) > 0, "set_updated_at() COMMENT must be non-empty (Uhura-1)"
    assert "BEFORE UPDATE" in comment, (
        f"Function COMMENT must reference BEFORE UPDATE semantics; got: {comment!r}"
    )


# =============================================================================
# Group 2: Per-table maintenance functions are GONE
# =============================================================================


@pytest.mark.parametrize(
    "function_name",
    [
        "update_canonical_markets_updated_at",
        "update_canonical_market_links_updated_at",
        "update_canonical_event_links_updated_at",
    ],
)
def test_per_table_function_dropped(db_pool: Any, function_name: str) -> None:
    """The 3 per-table maintenance functions MUST be dropped by Migration 0076."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE p.proname = %s
              AND n.nspname = 'public'
            """,
            (function_name,),
        )
        row = cur.fetchone()
    assert row is None, (
        f"{function_name}() must NOT exist post-Migration-0076 (replaced by "
        f"generic set_updated_at())"
    )


# =============================================================================
# Group 3: Trigger instances all dispatch to the generic function
# =============================================================================


@pytest.mark.parametrize("table_name", _RETROFIT_TABLES)
def test_trigger_dispatches_to_set_updated_at(db_pool: Any, table_name: str) -> None:
    """Each retrofitted table's BEFORE UPDATE trigger calls ``set_updated_at()``.

    Trigger names are preserved as ``trg_<table>_updated_at`` (Migration 0072
    carry-forward); only the EXECUTE FUNCTION target changes from per-table to
    generic.
    """
    trigger_name = f"trg_{table_name}_updated_at"
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_triggerdef(t.oid) AS def
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            WHERE c.relname = %s
              AND t.tgname = %s
              AND NOT t.tgisinternal
            """,
            (table_name, trigger_name),
        )
        row = cur.fetchone()
    assert row is not None, f"{trigger_name} must exist on {table_name} post-Migration-0076"
    trigger_def = row["def"]
    assert "BEFORE UPDATE" in trigger_def, (
        f"{trigger_name} must be a BEFORE UPDATE trigger; got: {trigger_def}"
    )
    assert "set_updated_at" in trigger_def, (
        f"{trigger_name} must call set_updated_at(); got: {trigger_def}"
    )


# =============================================================================
# Group 4: Behavioral fire-on-UPDATE (Miles M-5 -- non-negotiable)
#
# INSERT row, sleep briefly so transaction_timestamp advances across separate
# commit=True transactions, UPDATE without explicit updated_at, assert
# updated_at advanced.  Mirrors the test_migration_0069 / test_migration_0072
# *_advances_updated_at pattern at the same depth.  Strict ``>`` (not ``>=``)
# per Ripley sentinel session 80 P1 -- catches no-op trigger function body.
# =============================================================================


def test_canonical_events_trigger_advances_updated_at(db_pool: Any) -> None:
    """UPDATE on ``canonical_events`` advances ``updated_at`` per the new trigger.

    NET-NEW BEHAVIORAL COVERAGE: pre-Migration-0076, ``canonical_events``
    had no BEFORE UPDATE trigger (orphan-trigger gap from Migration 0067).
    Post-Migration-0076 the trigger is in place.  This test exercises the
    gap-closure behavior end-to-end.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT updated_at FROM canonical_events WHERE id = %s",
                (seeded_event_id,),
            )
            initial_updated_at = cur.fetchone()["updated_at"]

        # Sleep briefly so the transaction_timestamp ``now()`` advances
        # across the two separate ``commit=True`` transactions.  10ms is
        # well above PostgreSQL's microsecond-resolution clock granularity.
        time.sleep(0.01)

        # UPDATE a non-updated_at column; trigger should refresh updated_at.
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE canonical_events SET title = %s WHERE id = %s",
                (f"Updated test event ({suffix})", seeded_event_id),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT updated_at FROM canonical_events WHERE id = %s",
                (seeded_event_id,),
            )
            post_updated_at = cur.fetchone()["updated_at"]

        # Strict ``>`` per Ripley sentinel session 80 P1 -- catches no-op
        # trigger-function-body case at this layer.
        assert post_updated_at > initial_updated_at, (
            f"updated_at must advance (BEFORE UPDATE trigger no-op suspected); "
            f"initial={initial_updated_at!r}, post={post_updated_at!r}"
        )
    finally:
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_markets_trigger_advances_updated_at(db_pool: Any) -> None:
    """UPDATE on ``canonical_markets`` advances ``updated_at`` post-retrofit.

    Pattern 22-style refresh: confirms the rewired trigger preserves the
    pre-retrofit per-table behavior.
    """
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    nk_hash = f"TEST-1074-mkt-{suffix}".encode()
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_markets
                    (canonical_event_id, market_type_general, natural_key_hash)
                VALUES (%s, 'binary', %s)
                RETURNING id, updated_at
                """,
                (seeded_event_id, nk_hash),
            )
            row = cur.fetchone()
            market_id = int(row["id"])
            initial_updated_at = row["updated_at"]

        time.sleep(0.01)

        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE canonical_markets SET outcome_label = %s WHERE id = %s",
                ("test_outcome_0076", market_id),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT updated_at FROM canonical_markets WHERE id = %s",
                (market_id,),
            )
            post_updated_at = cur.fetchone()["updated_at"]
        assert post_updated_at > initial_updated_at, (
            f"updated_at must advance; initial={initial_updated_at!r}, post={post_updated_at!r}"
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_markets WHERE canonical_event_id = %s",
                (seeded_event_id,),
            )
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_market_links_trigger_advances_updated_at(db_pool: Any) -> None:
    """UPDATE on ``canonical_market_links`` advances ``updated_at`` post-retrofit."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_market_id = _seed_canonical_market(seeded_event_id, suffix)
    seeded_platform_market_id = _seed_platform_market(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_market_links (
                    canonical_market_id, platform_market_id, link_state,
                    confidence, algorithm_id, decided_by
                ) VALUES (%s, %s, 'active', 1.000, %s, %s)
                RETURNING id, updated_at
                """,
                (seeded_market_id, seeded_platform_market_id, algorithm_id, "system:test"),
            )
            row = cur.fetchone()
            link_id = int(row["id"])
            initial_updated_at = row["updated_at"]

        time.sleep(0.01)

        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                UPDATE canonical_market_links
                SET link_state = 'retired', retired_at = now()
                WHERE id = %s
                """,
                (link_id,),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT updated_at FROM canonical_market_links WHERE id = %s",
                (link_id,),
            )
            post_updated_at = cur.fetchone()["updated_at"]
        assert post_updated_at > initial_updated_at, (
            f"updated_at must advance; initial={initial_updated_at!r}, post={post_updated_at!r}"
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_market_links WHERE canonical_market_id = %s",
                (seeded_market_id,),
            )
        _cleanup_platform_market(seeded_platform_market_id)
        _cleanup_canonical_market(seeded_market_id)
        _cleanup_canonical_event(seeded_event_id)


def test_canonical_event_links_trigger_advances_updated_at(db_pool: Any) -> None:
    """UPDATE on ``canonical_event_links`` advances ``updated_at`` post-retrofit."""
    suffix = uuid.uuid4().hex[:8]
    seeded_event_id = _seed_canonical_event(suffix)
    seeded_platform_event_id = _seed_platform_event(suffix)
    algorithm_id = _get_manual_v1_algorithm_id()
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO canonical_event_links (
                    canonical_event_id, platform_event_id, link_state,
                    confidence, algorithm_id, decided_by
                ) VALUES (%s, %s, 'active', 1.000, %s, %s)
                RETURNING id, updated_at
                """,
                (seeded_event_id, seeded_platform_event_id, algorithm_id, "system:test"),
            )
            row = cur.fetchone()
            link_id = int(row["id"])
            initial_updated_at = row["updated_at"]

        time.sleep(0.01)

        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                UPDATE canonical_event_links
                SET link_state = 'retired', retired_at = now()
                WHERE id = %s
                """,
                (link_id,),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT updated_at FROM canonical_event_links WHERE id = %s",
                (link_id,),
            )
            post_updated_at = cur.fetchone()["updated_at"]
        assert post_updated_at > initial_updated_at, (
            f"updated_at must advance; initial={initial_updated_at!r}, post={post_updated_at!r}"
        )
    finally:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM canonical_event_links WHERE canonical_event_id = %s",
                (seeded_event_id,),
            )
        _cleanup_platform_event(seeded_platform_event_id)
        _cleanup_canonical_event(seeded_event_id)
