"""Migration round-trip CI gate — schema reversibility for migrations 0067 onward.

Programmatic CI gate that, for every Alembic revision ``R`` from ``0067`` up
to ``head``, exercises a ``downgrade(R.down_revision) -> upgrade head``
round-trip and asserts the post-round-trip schema state is byte-identical to
the pre-round-trip state.  Catches three classes of bug that the prior manual
round-trip discipline (Samwise hand-runs on each Cohort 1/2/3 migration) cannot
detect at PR time:

    1. **Non-reversible downgrade**: a migration's ``downgrade()`` step omits
       a DROP for something the ``upgrade()`` step CREATEd (constraint, index,
       trigger, sequence).  Schema lingers; later migrations fail or silently
       drift.
    2. **Asymmetric DDL**: ``upgrade()`` creates a column with one default /
       nullability, ``downgrade()`` drops the column, but the re-applied
       ``upgrade()`` (post-downgrade) recreates it with a slightly different
       shape (e.g., a missed ``NOT NULL``, a typo in a default expression).
    3. **Append-only-migrations principle violation**: a migration that
       MUTATES a previously-shipped revision's behavior (Pattern 87
       candidate; ADR-118 V2.42 — ``#1069``) — round-trip exposes the
       cumulative mutation as a snapshot diff between the initial head state
       and the post-round-trip head state.

What this gate does NOT cover (out-of-scope; tracked separately):

    *********************************************************************
    *  WARNING — A GREEN RUN OF THIS GATE DOES NOT CERTIFY THAT          *
    *  DOWNGRADE IS SAFE TO RUN IN PRODUCTION.                           *
    *                                                                    *
    *  The gate is SCHEMA-ONLY by design.  Rows in DROP'd tables are     *
    *  permanently lost on downgrade.  Data persistence is verified by   *
    *  Epic #1071's separate backup/restore drill issue (#1067) — NOT    *
    *  by this gate.                                                     *
    *                                                                    *
    *  If you are reading a CI badge labeled "Migration round-trip CI    *
    *  gate" PASS and inferring "downgrade is safe in prod", STOP.       *
    *  That is the wrong inference.  The gate verifies that              *
    *  upgrade()/downgrade() are inverses at the schema level — nothing  *
    *  about row data, application invariants, or operational safety.    *
    *********************************************************************

    * **Row-data persistence after destructive downgrade.** See banner above.
      Tracked by Epic #1071 backup/restore drill (#1067).
    * **Migrations 0001-0066** (well-trodden production-shipped surface).
      Lower bound is ``0067`` per Issue ``#1066`` — the new architecture
      surface (Cohort 1+) is the risk envelope.
    * **Cross-database divergence** (PG vs. cloud-managed PG).  Gate runs
      against the CI ``postgres:15`` service; if a managed-PG variant ships
      differently (e.g., an extension is unavailable), that is a separate
      pre-prod harness concern (Epic ``#1071`` items 4-6).
    * **Schema artifacts NOT YET in the snapshot oracle:** views
      (``CREATE VIEW`` / ``CREATE MATERIALIZED VIEW``), generated columns
      (``GENERATED ALWAYS AS``), partitioning (``PARTITION BY``), enum
      types (``CREATE TYPE ... AS ENUM``), domain types, extensions
      (``CREATE EXTENSION``), table/column comments.  None of these are
      used in migrations 0067-0071 (verified at gate-build time, session 80
      Ripley sentinel sweep).  Forecasted to land in Cohort 3 slots 0072+
      (canonical projection views) and Cohort 7+ (canonical_observations
      partitioning).  Gate must add coverage BEFORE the first migration
      using one of these constructs ships, or it false-passes that
      migration.  Tracked under Epic #1071 follow-up issues filed in PR.

Test sequence per migration (parametrized; one test case per revision):

    1. Precondition: ``alembic_version`` is at ``head`` (from the prior test
       OR the integration-tests CI step that pre-applies migrations to head
       before pytest runs — see ``.github/workflows/ci.yml`` lines 402-413).
    2. Snapshot 1: ``_capture_schema_snapshot()`` — full schema state
       (tables, columns, constraints, indexes, triggers, sequences).
    3. Round-trip for revision R:
       ``alembic.command.downgrade(cfg, R.down_revision)`` ->
       ``alembic.command.upgrade(cfg, 'head')``.  This exercises R's
       ``downgrade()`` in isolation (plus any subsequent revisions'
       downgrades, which step down through R's down_revision).  Uses the
       Alembic Python API rather than subprocess CLI for cleaner exception
       propagation.

       Build-time correction (Samwise probe, 2026-04-26): the issue's
       prose said "downgrade -1" but a literal ``downgrade(cfg, '-1')``
       from head only ever exercises the HIGHEST-revision downgrade (e.g.,
       0071's), regardless of the parametrize ID — every test would
       silently exercise the same migration.  Correct semantics: step
       down to ``R.down_revision`` for revision ``R`` so that R's
       ``downgrade()`` is the one that actually runs.
    4. Snapshot 2: re-capture.
    5. Equality assertion: ``snapshot_1 == snapshot_2`` with diff helpers
       reporting added / removed / changed entries (pytest's default repr
       is sufficient for cross-section diffs).
    6. Postcondition: ``alembic_version`` is back at ``head`` so the next
       parametrized case starts from a known state.
    7. Per-test timing log: ``time.perf_counter()`` delta surfaced via
       ``logging.info`` so CI captures per-migration timings (visible in
       ``pytest -v`` output).

Edge case — cascading failures: if test ``N`` fails partway through (e.g.,
the ``downgrade`` step raises), the DB is left in an indeterminate state
and test ``N+1``'s precondition assert fires.  This is intentional — the
cascade points at the ORIGINAL broken downgrade.  An autouse finalizer
attempts best-effort recovery (``upgrade head``) after every test; if that
itself fails, subsequent test failures remain informative.

Implicit dependency this gate is itself designed to catch when it bit-rots:
the Alembic Python API surface (``alembic.command.upgrade`` /
``alembic.command.downgrade`` / ``alembic.script.ScriptDirectory``) is
stable across the 1.x line.  If a future Alembic upgrade breaks the import
shape, the gate fires at collect time, not silently — that is the desired
failure mode.

Issue: ``#1066`` (P0 — Migration round-trip CI gate)
Epic: ``#1071`` (Pre-prod migration safety harness)
ADR: ADR-118 V2.42 (Cohort 1-3 canonical layer foundations); Pattern 87 (append-only-migrations, ``#1069``)

Markers:
    @pytest.mark.integration: real DB required; mirrors sibling
        ``tests/integration/database/test_migration_*.py`` discipline.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from precog.database.connection import get_cursor
from precog.database.connection import test_connection as check_db_connection

# Skip all tests if database not available — mirrors
# tests/integration/database/test_migration_idempotency.py discipline (sibling
# migration-flavored integration test in the suite).
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not check_db_connection(), reason="Database connection not available"),
]

logger = logging.getLogger(__name__)

# Lower bound per Issue #1066: round-trip every migration from 0067 onward.
# Migrations 0001-0066 are well-trodden production-shipped surface; the new
# canonical-layer architecture (Cohort 1+) is the risk envelope this gate
# protects.  The string "0066" is the BASE argument to walk_revisions; the
# semantics of that call are documented at the canonical SSOT in
# `_get_revisions_to_test()` (head-first inclusive of base), and this comment
# does not restate them.
_LOWER_BOUND_BASE_REVISION: str = "0066"


# =============================================================================
# Alembic config + revision discovery
# =============================================================================


def _get_alembic_config() -> Config:
    """Return a configured ``alembic.config.Config`` rooted at the repo's
    ``src/precog/database/alembic.ini``.

    Resolves the ini path via ``Path(__file__).parents[N]`` rather than via
    a relative ``cwd`` lookup — pytest's working directory is the repo root,
    not ``src/precog/database/``, so the bare string ``'alembic.ini'`` would
    fail.

    Build-time discovery (Samwise probe, 2026-04-26): the
    ``script_location = alembic`` value in alembic.ini (line 6) is resolved
    by Alembic **relative to the current working directory**, NOT relative
    to the ini file's location.  Naively constructing ``Config(ini_path)``
    therefore fails when pytest's cwd is the repo root with
    ``CommandError: Path doesn't exist: '<repo_root>/alembic'``.  Fix:
    explicitly set ``main_option('script_location', ...)`` to the absolute
    ``src/precog/database/alembic`` path so the resolution becomes
    cwd-independent.  Documented behavior; not a bug.
    """
    repo_root = Path(__file__).resolve().parents[3]
    db_dir = repo_root / "src" / "precog" / "database"
    ini_path = db_dir / "alembic.ini"
    script_path = db_dir / "alembic"
    assert ini_path.is_file(), (
        f"alembic.ini not found at {ini_path}; "
        "directory layout has drifted — round-trip gate cannot resolve config"
    )
    assert script_path.is_dir(), (
        f"alembic script directory not found at {script_path}; "
        "directory layout has drifted — round-trip gate cannot resolve config"
    )
    cfg = Config(str(ini_path))
    # Override the relative script_location with the absolute path so that
    # ScriptDirectory.from_config + command.upgrade work regardless of cwd.
    cfg.set_main_option("script_location", str(script_path))
    return cfg


def _get_revisions_to_test() -> list[str]:
    """Return the ordered list of revision identifiers to round-trip.

    Walks the revision chain from ``head`` back toward (and including)
    ``_LOWER_BOUND_BASE_REVISION``, then slices off the base to keep only
    revisions ABOVE it.  Returns revisions in head-first order
    (e.g., ``['0071', '0070', '0069', '0068', '0067']``); we reverse to
    bottom-up order (``['0067', ..., '0071']``) so test parametrize IDs
    sort intuitively in pytest -v output and the round-trips proceed in
    revision-chain order.

    Probe verification (Samwise build-time check, 2026-04-26):
        ``walk_revisions('0066', 'head')`` returns 6 revisions from
        head down to and INCLUDING the base (``0066`` itself).  Slicing
        ``[:-1]`` drops ``0066``, leaving exactly 5 revisions
        (``0067``..``0071``).
    """
    cfg = _get_alembic_config()
    script = ScriptDirectory.from_config(cfg)
    head_first = list(script.walk_revisions(_LOWER_BOUND_BASE_REVISION, "head"))
    # Drop the inclusive base (0066) — issue #1066 specifies "0067 onward".
    above_base = head_first[:-1]
    # Reverse to bottom-up order for intuitive parametrize IDs.
    return [s.revision for s in reversed(above_base)]


# =============================================================================
# Schema snapshot — the equality oracle
# =============================================================================


def _capture_schema_snapshot(cur: Any) -> dict[str, list[tuple[Any, ...]]]:
    """Capture a comparable, deterministic snapshot of the public-schema state.

    The snapshot is **schema-only** by design — it does NOT include row data.
    See module docstring for the rationale and the cross-reference to Epic
    ``#1071``'s separate backup/restore drill.

    Returns a dict with seven sorted-list values keyed:

        - ``tables``: ``(schema, table_name)``
        - ``columns``: ``(table_name, column_name, data_type, udt_name,
            is_nullable, column_default, character_maximum_length,
            numeric_precision, numeric_scale)`` — ``udt_name`` is the
            load-bearing disambiguator for ARRAY columns (``data_type``
            returns the literal ``'ARRAY'`` for all arrays; ``udt_name``
            distinguishes ``_int4`` vs ``_int8`` etc.).
        - ``constraints``: ``(table_name, constraint_name, constraint_type,
            constraint_def)`` — ``constraint_def`` from
            ``pg_get_constraintdef(oid)`` so column lists, ON DELETE
            actions, and CHECK expressions all participate in equality.
        - ``indexes``: ``(table_name, index_name, index_def)`` —
            ``index_def`` from ``pg_get_indexdef(oid)`` so column lists,
            partial WHERE clauses, and sort orders all participate.
        - ``triggers``: ``(table_name, trigger_name, action_statement,
            action_timing, event_manipulation)``
        - ``functions``: ``(function_name, function_def)`` —
            ``function_def`` from ``pg_get_functiondef(oid)`` so the
            FULL function body participates in equality.  Load-bearing
            for the gate's stated Class 2 failure mode (asymmetric DDL):
            without this section, a ``CREATE OR REPLACE FUNCTION foo()``
            with a corrupted body would round-trip to the same
            ``trigger.action_statement`` reference (``EXECUTE FUNCTION
            foo()``) and FALSE-PASS.  Migrations 0068 + 0069 already
            ship two functions in production
            (``enforce_canonical_entity_team_backref()``,
            ``update_canonical_markets_updated_at()``); slot 0076+
            issue #1074 adds a generic ``set_updated_at()`` retrofit.
            Ripley sentinel finding (P0).
        - ``sequences``: ``(sequence_name, data_type, start_value,
            increment, max_value)``

    All result rows are sorted to make ``snapshot_1 == snapshot_2`` a stable
    equality check (PostgreSQL's catalog query order is not specified).

    Excludes ``alembic_version`` from the ``tables`` / ``columns`` slices —
    its single ``version_num`` row content varies across the round-trip
    (it is the very thing the round-trip mutates) but the table itself
    re-appears identically.  We assert ``alembic_version`` table presence
    + version equality separately in ``_assert_at_head``.
    """
    snapshot: dict[str, list[tuple[Any, ...]]] = {}

    # 1. Tables (schema-qualified)
    cur.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name
        """
    )
    snapshot["tables"] = sorted((row["table_schema"], row["table_name"]) for row in cur.fetchall())

    # 2. Columns (full shape).  ``udt_name`` is the load-bearing
    # disambiguator for ARRAY columns: ``information_schema.columns.data_type``
    # returns the literal string ``'ARRAY'`` for any array type, so a future
    # migration changing ``INTEGER[]`` to ``BIGINT[]`` (e.g.,
    # ``canonical_events.entities_sorted``) would otherwise round-trip as
    # equal at the snapshot level.  ``udt_name`` distinguishes ``_int4`` from
    # ``_int8`` and similar.
    cur.execute(
        """
        SELECT
            table_name,
            column_name,
            data_type,
            udt_name,
            is_nullable,
            column_default,
            character_maximum_length,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, column_name
        """
    )
    snapshot["columns"] = sorted(
        (
            row["table_name"],
            row["column_name"],
            row["data_type"],
            row["udt_name"],
            row["is_nullable"],
            row["column_default"],
            row["character_maximum_length"],
            row["numeric_precision"],
            row["numeric_scale"],
        )
        for row in cur.fetchall()
    )

    # 3. Constraints — pg_get_constraintdef captures column lists, ON DELETE,
    # CHECK expressions, etc.  Equality across that string is load-bearing.
    cur.execute(
        """
        SELECT
            cls.relname AS table_name,
            con.conname AS constraint_name,
            con.contype AS constraint_type,
            pg_get_constraintdef(con.oid) AS constraint_def
        FROM pg_constraint con
        JOIN pg_class cls ON cls.oid = con.conrelid
        JOIN pg_namespace ns ON ns.oid = cls.relnamespace
        WHERE ns.nspname = 'public'
        ORDER BY cls.relname, con.conname
        """
    )
    snapshot["constraints"] = sorted(
        (
            row["table_name"],
            row["constraint_name"],
            row["constraint_type"],
            row["constraint_def"],
        )
        for row in cur.fetchall()
    )

    # 4. Indexes — pg_get_indexdef captures partial WHERE, column lists,
    # sort orders, and operator classes.
    cur.execute(
        """
        SELECT
            cls.relname AS table_name,
            ic.relname AS index_name,
            pg_get_indexdef(idx.indexrelid) AS index_def
        FROM pg_index idx
        JOIN pg_class ic ON ic.oid = idx.indexrelid
        JOIN pg_class cls ON cls.oid = idx.indrelid
        JOIN pg_namespace ns ON ns.oid = cls.relnamespace
        WHERE ns.nspname = 'public'
        ORDER BY cls.relname, ic.relname
        """
    )
    snapshot["indexes"] = sorted(
        (row["table_name"], row["index_name"], row["index_def"]) for row in cur.fetchall()
    )

    # 5. Triggers — action_statement contains the body / function call;
    # action_timing + event_manipulation pin BEFORE/AFTER + INSERT/UPDATE/DELETE.
    cur.execute(
        """
        SELECT
            event_object_table AS table_name,
            trigger_name,
            action_statement,
            action_timing,
            event_manipulation
        FROM information_schema.triggers
        WHERE trigger_schema = 'public'
        ORDER BY event_object_table, trigger_name, event_manipulation
        """
    )
    snapshot["triggers"] = sorted(
        (
            row["table_name"],
            row["trigger_name"],
            row["action_statement"],
            row["action_timing"],
            row["event_manipulation"],
        )
        for row in cur.fetchall()
    )

    # 6. Functions — full body via pg_get_functiondef.  Load-bearing for the
    # gate's stated Class 2 failure mode (asymmetric DDL): without this, a
    # CREATE OR REPLACE FUNCTION with a corrupted body false-passes the
    # round-trip because the trigger's action_statement reference is
    # unchanged.  Filter to user-defined regular functions in the public
    # schema (prokind='f') — excludes aggregates, window functions, and
    # internal procedures.  Ripley sentinel P0 (Joe Chip P1, reframed).
    cur.execute(
        """
        SELECT
            p.proname AS function_name,
            pg_get_functiondef(p.oid) AS function_def
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.prokind = 'f'
        ORDER BY p.proname
        """
    )
    snapshot["functions"] = sorted(
        (row["function_name"], row["function_def"]) for row in cur.fetchall()
    )

    # 7. Sequences — start / increment / max values.  Note: ``last_value``
    # is INTENTIONALLY excluded — it advances on every nextval() call and
    # would cause the snapshot to diff after any test that touches a
    # SERIAL/BIGSERIAL column, defeating the equality check.  Schema
    # reversibility is what we measure; sequence cursor position is
    # transactional state.
    cur.execute(
        """
        SELECT
            sequence_name,
            data_type,
            start_value,
            increment,
            maximum_value
        FROM information_schema.sequences
        WHERE sequence_schema = 'public'
        ORDER BY sequence_name
        """
    )
    snapshot["sequences"] = sorted(
        (
            row["sequence_name"],
            row["data_type"],
            row["start_value"],
            row["increment"],
            row["maximum_value"],
        )
        for row in cur.fetchall()
    )

    return snapshot


def _diff_snapshots(
    snap_before: dict[str, list[tuple[Any, ...]]],
    snap_after: dict[str, list[tuple[Any, ...]]],
) -> str:
    """Return a human-readable diff between two snapshots.

    Walks each section (tables / columns / constraints / indexes / triggers /
    sequences) and emits added / removed entries.  Used in the assertion
    failure message so a CI failure shows EXACTLY what drifted, rather than
    relying on pytest's default-repr of two large dicts (which truncates).
    """
    lines: list[str] = []
    for section in (
        "tables",
        "columns",
        "constraints",
        "indexes",
        "triggers",
        "functions",
        "sequences",
    ):
        before = set(snap_before.get(section, []))
        after = set(snap_after.get(section, []))
        added = sorted(after - before)
        removed = sorted(before - after)
        if added or removed:
            lines.append(f"  [{section}] {len(added)} added, {len(removed)} removed")
            for entry in removed:
                lines.append(f"    - REMOVED: {entry!r}")
            for entry in added:
                lines.append(f"    + ADDED:   {entry!r}")
    if not lines:
        return "    (no diff — but snapshots compared unequal — check ordering invariants)"
    return "\n".join(lines)


# =============================================================================
# Alembic version assertions
# =============================================================================


def _read_alembic_version(cur: Any) -> str | None:
    """Return the current ``alembic_version.version_num`` value, or ``None``
    if the table does not exist (DB never had migrations applied).

    Resolves the version-table NAME from the live alembic config rather than
    hardcoding ``'alembic_version'`` — a future deploy splitting prod / dev
    migration histories via ``version_table = alembic_version_canonical`` in
    alembic.ini would otherwise silently route this gate to a non-existent
    table and return None on every call.  Falls back to the Alembic default
    (``'alembic_version'``) when the option is unset.  Joe Chip P1 #3.
    """
    cfg = _get_alembic_config()
    table_name = cfg.get_main_option("version_table") or "alembic_version"
    # SQL identifier interpolation: pg's ``information_schema.tables.table_name``
    # accepts a parameter-bound literal; the ``FROM`` clause name needs Python
    # string interpolation — guarded by the cfg-derived value (not user input).
    cur.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        ) AS exists
        """,
        (table_name,),
    )
    if not cur.fetchone()["exists"]:
        return None
    # Identifier (table name) cannot be parameterized in psycopg2; cfg-derived
    # so safe.  Use ``psycopg2.sql.Identifier`` if/when this becomes a concern.
    cur.execute(f"SELECT version_num FROM {table_name}")  # noqa: S608 — cfg-derived literal
    row = cur.fetchone()
    return row["version_num"] if row else None


def _expected_head_revision() -> str:
    """Return the current Alembic ``head`` revision identifier as a string."""
    script = ScriptDirectory.from_config(_get_alembic_config())
    head = script.get_current_head()
    assert head is not None, (
        "ScriptDirectory.get_current_head() returned None — "
        "no head revision discoverable.  Migration chain is broken."
    )
    return head


def _assert_at_head(cur: Any, context: str) -> None:
    """Assert the DB's ``alembic_version`` matches the expected head.

    ``context`` is included in the assertion message so a failure tells the
    reader WHICH stage of the test sequence failed (precondition vs.
    postcondition).
    """
    actual = _read_alembic_version(cur)
    expected = _expected_head_revision()
    assert actual == expected, (
        f"alembic_version mismatch ({context}): "
        f"expected {expected!r}, got {actual!r}.  "
        "If this fires on the FIRST parametrized test, the integration-tests "
        "CI step that pre-applies migrations to head (ci.yml lines 402-413) "
        "may have failed silently OR a prior parametrized test left the DB "
        "in an indeterminate state."
    )


# =============================================================================
# Best-effort recovery — runs after every parametrized test
# =============================================================================


@pytest.fixture(autouse=True)
def _restore_to_head_after_each_test() -> Any:
    """Best-effort: after each test, ensure the DB is back at ``head``.

    If a test fails partway through (e.g., ``command.downgrade(cfg, '-1')``
    raises), the DB is left in an indeterminate state.  Without recovery,
    the next test's precondition assert fires too — cascading failures.
    The cascade is informative (it points at the original broken downgrade)
    but also drowns the signal under noise.

    This finalizer attempts ``alembic upgrade head`` after each test.  If
    THAT itself fails (e.g., the broken downgrade left a partial state
    Alembic can't recover from), we swallow the exception and let the next
    test's precondition assert fire — that is the desired failure mode for
    a wedged DB.

    **Wedge-immunity dependency (Ripley sentinel finding):** the gate's
    immunity to the "snapshot_before == snapshot_after on a broken state"
    false-pass mode REQUIRES that every migration's ``downgrade()`` uses
    ``IF EXISTS`` discipline (Pattern 87 + ``feedback_idempotent_migration_drops.md``).
    A future migration shipping a non-idempotent downgrade can construct a
    wedge where: (a) the test's downgrade raises mid-execution, (b) the
    autouse retry's upgrade also raises, (c) Alembic's ``alembic_version``
    has been bumped to head despite a partial schema state, and (d) the
    next test reads ``alembic_version=head`` AND captures snapshots of
    the same partial state on both sides of a no-op round-trip → false-pass.
    The IF EXISTS discipline closes this by making downgrades idempotent;
    review of every new downgrade()'s DROP statements for IF EXISTS
    coverage is the structural enforcement (caught at PR-time review,
    not at runtime).
    """
    yield  # run the test
    try:
        cfg = _get_alembic_config()
        command.upgrade(cfg, "head")
    except Exception as exc:
        logger.warning(
            "Best-effort recovery to head failed after test: %s. "
            "Subsequent tests' precondition asserts will fire.",
            exc,
        )


# =============================================================================
# The gate
# =============================================================================


# Compute revisions at module-import time so pytest can build the parametrize
# IDs at collection time.  This means a broken migration chain fails at
# COLLECT, not RUN — which is the right failure mode (no test fires, which
# would otherwise look like everything-passed-because-nothing-ran).
_REVISIONS_TO_TEST: list[str] = _get_revisions_to_test()


@pytest.mark.parametrize("revision", _REVISIONS_TO_TEST)
def test_round_trip_preserves_schema_for_revision(
    db_pool: Any,
    revision: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Round-trip ``downgrade -> upgrade head`` for revision ``R`` preserves schema.

    For revision ``{revision}``:
        1. Precondition: DB is at head (verified via ``alembic_version``).
        2. Snapshot the schema (tables / columns / constraints / indexes /
           triggers / sequences).
        3. ``downgrade(R.down_revision)`` — exercises R's ``downgrade()``
           step (plus any higher-revision downgrades on the way down).
        4. ``upgrade head`` — exercises R's ``upgrade()`` step (plus any
           higher-revision upgrades on the way back up).
        5. Re-snapshot.
        6. Assert snapshot equality — the ROUND-TRIP must be a no-op at the
           schema level.  Inequality means ``upgrade()`` and ``downgrade()``
           are not inverses for some revision in the [R..head] window
           (Issue #1066's three failure classes — see module docstring).
        7. Postcondition: DB is back at head.

    Note on exclusivity: each test parametrize case isolates the FIRST
    incremental window that exercises revision R's down/up pair.  When R
    is the head itself, this is a single-step round-trip; when R is the
    bottom of the window, it is a 5-step round-trip.  Schema equality
    must hold at every level — so a regression introduced by ANY
    revision in the window surfaces somewhere.

    Implicit dependencies this test surfaces if they break (failure modes
    this gate is designed to catch when the underlying tooling drifts):

        - ``alembic.command.upgrade`` / ``alembic.command.downgrade`` API
          stability across the Alembic 1.x line.
        - ``alembic.script.ScriptDirectory.walk_revisions`` semantics
          (verified at build time on Alembic 1.15.2 — base argument is
          inclusive; we slice ``[:-1]`` to drop it).
        - ``Script.down_revision`` is a single string identifier (not a
          tuple of multi-parents); the canonical migration chain is
          linear, no branches.  If a future Alembic merge-revision
          ships, ``down_revision`` becomes a tuple and this code must
          adapt — caught by the assertion below.
        - PostgreSQL ``information_schema`` + ``pg_catalog`` view stability
          across the supported PG versions (CI uses ``postgres:15``).
    """
    cfg = _get_alembic_config()
    script = ScriptDirectory.from_config(cfg)
    rev_obj = script.get_revision(revision)
    assert rev_obj is not None, (
        f"ScriptDirectory.get_revision({revision!r}) returned None — "
        "revision identifier drifted between collection time and run time."
    )
    down_target = rev_obj.down_revision
    assert isinstance(down_target, str), (
        f"Revision {revision!r}.down_revision is not a single string "
        f"(got {type(down_target).__name__}); two cases this can hit:\n"
        f"  (a) None — revision is the chain base (no parent to downgrade to).\n"
        f"      Lower the gate's ``_LOWER_BOUND_BASE_REVISION`` if base coverage\n"
        f"      is desired.\n"
        f"  (b) tuple — the migration chain has acquired a branch / merge.\n"
        f"      Update this gate's downgrade target logic to handle multi-parent\n"
        f"      revisions before it can run."
    )

    # Step 1: Precondition — DB at head.
    with get_cursor() as cur:
        _assert_at_head(cur, context=f"precondition before round-trip of {revision}")

    # Step 2: Snapshot the initial state.
    with get_cursor() as cur:
        snapshot_before = _capture_schema_snapshot(cur)

    # Step 3 + 4: Round-trip via Alembic Python API.  Downgrade target is
    # ``R.down_revision``, NOT the literal string ``-1`` — see step 3 in
    # the module docstring's test sequence for the rationale.
    #
    # Cleaner exception propagation than subprocess CLI — failures land here
    # as the original Alembic exception type, not a CalledProcessError with
    # stderr text we'd have to parse.
    t_start = time.perf_counter()
    try:
        command.downgrade(cfg, down_target)
        command.upgrade(cfg, "head")
    except Exception:
        # Re-raise as-is — pytest will surface the Alembic exception type
        # and traceback.  The autouse finalizer will attempt recovery.
        raise
    finally:
        elapsed = time.perf_counter() - t_start
        # Per-test timing — visible in `pytest -v` output via
        # `--log-cli-level=INFO`.  Useful when the gate's total runtime
        # starts approaching the 15-min CI integration-tests timeout.
        logger.info(
            "round-trip [%s]: downgrade to %s + upgrade head took %.3fs",
            revision,
            down_target,
            elapsed,
        )

    # Step 5: Re-snapshot.
    with get_cursor() as cur:
        snapshot_after = _capture_schema_snapshot(cur)

    # Step 6: Equality assertion with explicit diff for failure mode.
    if snapshot_before != snapshot_after:
        diff = _diff_snapshots(snapshot_before, snapshot_after)
        pytest.fail(
            f"Round-trip schema drift for revision {revision!r}:\n"
            f"  downgrade({down_target!r}) -> upgrade head is NOT a no-op at the\n"
            f"  schema level.  This means revision {revision}'s upgrade() and\n"
            f"  downgrade() are not inverses (or a later revision MUTATES this\n"
            f"  one — Pattern 87 violation).\n"
            f"\n"
            f"  Drift detail:\n"
            f"{diff}\n"
        )

    # Step 7: Postcondition — DB back at head.
    with get_cursor() as cur:
        _assert_at_head(cur, context=f"postcondition after round-trip of {revision}")
