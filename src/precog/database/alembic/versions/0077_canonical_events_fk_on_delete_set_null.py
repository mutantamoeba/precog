"""Cohort 3 close-out post-retrofit -- canonical_events FK ON DELETE SET NULL
flip for ``game_id`` + ``series_id`` (#1075, ADR-118 V2.42 sub-amendment B).

Slot 0077 is the SECOND of two close-out post-retrofit migrations following
Cohort 3's main 5-slot arc (slots 0071-0075).  V2.42 sub-amendment A was
ratified in slot 0076 (generic ``set_updated_at()`` retrofit + canonical_events
orphan-trigger gap closure); sub-amendment B (this migration) flips the
``ON DELETE`` polarity on the two ``canonical_events`` FK references that
target the platform tier (``games`` and ``series``) from the Migration 0067
default ``NO ACTION`` to the canonical-tier-correct ``SET NULL``.

Council adjudication: SPLIT into 0076 + 0077 per session-83 design council
(Holden silent-fail vs loud-fail asymmetry + Miles failure-mode independence
+ rollback granularity).  Council synthesis at
``memory/design_review_0076_synthesis.md``.

FK polarity rationale (Holden + Galadriel + Miles + Uhura unanimous):

    ON DELETE SET NULL is the correct polarity for ``canonical_events.game_id``
    and ``canonical_events.series_id``.

    - **Not RESTRICT/NO ACTION** (the pre-retrofit default) -- would block
      ``games``/``series`` deletions even when the canonical event has matured
      past the platform-row dependency.  ADR-118 V2.38's "canonical-outlives-
      platform" framing specifically anticipates platform-row turnover
      (replays, retracted seasons, schedule corrections) without canonical-row
      destruction.
    - **Not CASCADE** -- would silently delete a canonical event when its
      platform game/series row is removed, which inverts the polarity
      ADR-118 enforces (canonical is the authoritative tier; platform rows
      are observations of it).  Catastrophic and irreversible.
    - **SET NULL** -- preserves the canonical row, NULLs the link, and the
      matcher (Cohort 5+) can re-bind.  Both columns are already NULLABLE
      (Migration 0067 ships them without ``NOT NULL``), so the polarity is
      type-compatible without column ALTER.

Cross-domain note (Galadriel cross-module audit):

    ``canonical_events`` rows for non-``sports`` domains
    (politics/weather/econ/news/entertainment/fighting) have
    ``game_id IS NULL`` and ``series_id IS NULL`` from creation by definition
    (Migration 0067 docstring: "most non-sports-domain events have NULL
    game_id").  SET NULL is a no-op for these rows (NULL -> NULL on parent
    DELETE is vacuous because the parent doesn't exist).  The retrofit is
    silent for ~83% of future canonical_events rows.

Production-Python-reader audit (Galadriel):

    ZERO production Python readers branch on ``canonical_events.game_id`` or
    ``canonical_events.series_id`` being non-NULL today.  Verified at build
    time via grep across ``src/precog/`` -- ``crud_canonical_events.py``
    helpers ``create``, ``get_by_id``, ``get_by_natural_key_hash``,
    ``retire`` all return the columns in the row dict but never branch on
    non-NULL; passthrough only.  No JOINs from ``canonical_events ->
    games/series`` exist in any production code path.  ``temporal_alignment_
    writer.py`` reads ``events.game_id`` (platform tier), NOT ``canonical_
    events.game_id``.  SET NULL is therefore safe for in-flight code.

Constraint-name preservation (Holden-FK):

    The DROP CONSTRAINT + ADD CONSTRAINT round-trip MUST re-add the FK
    constraints with their EXPLICIT original names
    (``canonical_events_game_id_fkey``, ``canonical_events_series_id_fkey``)
    -- if PG default-generates a name (e.g.,
    ``canonical_events_game_id_fkey1``), the
    ``test_migration_0067_canonical_events_foundation.py`` pinned-by-name
    assertion (lines 400-450) would break and any consumer that grepped for
    the constraint name would find the wrong row.  Re-using the original
    name is type-compatible with the test's parametrize values.

Pattern 73 SSOT (rule + pointers, never duplicated rule text):

    The ON DELETE polarity is defined ONCE per FK column in this migration's
    DDL.  The schema doc V2.3 § canonical_events column-level table cites
    this migration via Pattern 86 freshness marker.  ADR-118 V2.42 sub-
    amendment B carries the architectural decision rationale; the migration
    docstring (this block) carries the operational + audit-trail framing.
    Future readers asking "is canonical_events.game_id nullable?" should
    consult V2.3 (canonical living-doc), and asking "what's the SET NULL
    rationale?" should consult ADR-118 V2.42 sub-amendment B.

Pattern 81 (lookup convention) -- N/A this slot.  No lookup tables introduced.

Pattern 84 (two-phase NOT VALID + VALIDATE for CHECK on populated tables) --
N/A this slot.  Pattern 84's two-phase pattern targets CHECK constraints on
populated tables, not FK ALTER.  PostgreSQL does have a NOT VALID variant
for FKs, but the carve-out language ("when the table is empty") fires
either way: ``canonical_events`` has 0 rows in dev/staging/prod at slot-0077
deploy time (Cohort 1 shipped the table empty; no production deploy has
populated it yet; Cohort 5+ matcher pipeline begins writing AFTER this
slot).  Single-phase ALTER is correct (Holden-Pattern84).

Pattern 87 (append-only migrations) -- REAFFIRMED CLEAN.  Migrations 0001-
0076 are NOT edited by this PR.  The forward-pointer notes Galadriel cited
(Migration 0067 docstring referencing the FK polarity) are acknowledged
HERE in this migration's docstring per the Pattern 87 carve-out --
corrections to shipped migration docstrings live in the next migration's
docstring, not in the shipped one.  This PR's CRUD docstring sweep in
``crud_canonical_events.py`` + integration-test edits in
``test_migration_0067_canonical_events_foundation.py`` are NOT migration
files; they are application code + test code, both editable freely.

Populated-table FK retrofit forward-pointer (M-7, Miles):

    This migration is metadata-only at this slot because
    ``canonical_events`` is empty (zero rows in dev/staging/prod).  The
    ``ALTER TABLE ... DROP CONSTRAINT ... ADD CONSTRAINT`` round-trip
    acquires ``AccessExclusiveLock`` on canonical_events but performs no
    row scan -- the lock duration is bounded by metadata catalog updates
    (sub-second).

    For Cohort 7+ retrofits of similar FK polarity changes on POPULATED
    canonical tables (e.g., a future ``canonical_observations`` table with
    millions of rows), the runbook is:

        1. ``LOCK TABLE <table> IN SHARE ROW EXCLUSIVE MODE`` in a
           dedicated transaction.
        2. Run the ``ALTER TABLE ... DROP CONSTRAINT ... ADD CONSTRAINT``
           sequence.
        3. Verify the constraint re-creation succeeded; ROLLBACK on any
           error.
        4. Schedule the work in a low-traffic window (off-peak; matcher
           pipeline paused).

    PG12+ does NOT require a row rewrite for FK constraint changes (the
    constraint metadata is updated independently of row storage), but the
    ``AccessExclusiveLock`` duration becomes operationally observable on
    large tables.  This forward-pointer documents the runbook so a Cohort
    7+ author does not need to re-derive it.

Audit-trail breadcrumb deferral (Uhura-3):

    Post-retrofit, ``DELETE FROM games WHERE id = N`` cascades to
    ``canonical_events.game_id = NULL`` with ZERO forensic trace of who
    initiated the upstream DELETE or when (PostgreSQL provides no native
    "who triggered the cascade" audit signal).  The retrofitted BEFORE
    UPDATE trigger (slot 0076) fires (PG semantics: SET NULL is an UPDATE),
    bumping ``updated_at`` -- which tells you SOMETHING changed at time T
    but not WHAT and not WHY.  Indistinguishable from any other UPDATE.

    ``canonical_match_log`` (slot 0073) does NOT cover this -- it is
    market-tier-only per slot 0073 docstring lines 299-301 ("No
    ``canonical_event_log`` parallel -- Cohort 3 ledger is market-tier only
    at this stage").  Event-tier audit ledger is explicitly later-cohort
    scope.

    **No breadcrumb mechanism in slot 0077.**  Out of scope for V2.42 sub-
    amendment B (which scopes to FK polarity change only).  Forward-pointer:
    when a future cohort lands an ``canonical_event_log`` parallel to
    ``canonical_match_log``, that ledger will carry the SET NULL audit
    signal.  Documenting the asymmetry here so a future reader does not
    mistake the gap for an oversight.

    Application-layer mitigation: structured logs from the upstream DELETE
    path (e.g., a games-row deletion runbook) are the canonical actor
    record until the future-cohort event-tier audit ledger ships.

Reporting query gap + canonical query template (Uhura-2):

    Post-retrofit, the question "show me canonical_events whose game_id was
    NULLed in the past N days" becomes harder to answer from schema state
    alone.  The retrofitted ``updated_at`` trigger (slot 0076) advances on
    every UPDATE -- including SET NULL cascades AND including unrelated
    UPDATEs.  ``updated_at >= now() - INTERVAL 'N days' AND game_id IS NULL``
    is a noisy proxy: it includes events whose game_id was ALWAYS NULL and
    were updated for unrelated reasons in the window.

    Canonical query template for "show me canonical_events that became
    orphaned (game_id NULLed) recently":

        -- LIMITATION: This query approximates the orphaned-recently
        -- population via updated_at + IS NULL, but cannot distinguish
        -- "FK was NULLed today" from "FK was NULLed long ago, row was
        -- UPDATEd today for unrelated reasons."  Schema-state alone is
        -- insufficient; correlate with application logs from the
        -- upstream DELETE path for definitive forensics.
        SELECT id, domain_id, event_type_id, title,
               game_id, series_id, updated_at
        FROM canonical_events
        WHERE updated_at >= now() - INTERVAL '7 days'
          AND game_id IS NULL
        ORDER BY updated_at DESC;

    The honesty about the LIMITATION is load-bearing -- operators reading
    this query MUST understand it is a proxy, not a definitive answer.
    Pattern 73 SSOT pointer: this canonical-query template lives HERE in
    the migration docstring; CRUD-layer convenience helpers, if added,
    must point at this template rather than re-defining the SQL.

Cross-domain check (Galadriel cross-domain frame):

    Cross-domain NO-OP for ~83% of future canonical_events rows: non-sports
    domains (politics/weather/econ/news/entertainment/fighting) have
    ``game_id IS NULL`` and ``series_id IS NULL`` from creation by design.
    SET NULL on already-NULL is vacuous.  This retrofit is operationally
    silent for the majority of canonical_events rows; only the sports-
    domain subset (~17% of future rows per ADR-118 V2.38 + ADR-119
    domain-distribution forecast) carries non-NULL FKs that the SET NULL
    polarity actually exercises.

Cohort 5+ resolver implication (Galadriel cross-module frame):

    Cohort 5 will lazily resolve canonical_events from ``games`` rows via
    the matcher pipeline (ADR-118 Option A: ``canonical_event_id`` enricher
    column on ``games``).  Under this slot's SET NULL semantics, a
    ``DELETE FROM games WHERE id = N`` followed by a re-resolution will
    see ``canonical_events.game_id = NULL`` instead of FK-violation block.
    This is the INTENDED semantic per ADR-118 V2.42 sub-amendment B.

    Cohort 5 design MUST NOT cache canonical_events.game_id in resolver
    memory -- it can silently drift to NULL between cache fill and read.
    Forward-pointer for the future Cohort 5 design council: resolver code
    reads ``game_id`` at query time, never from cache.

Round-trip CI gate compatibility (PR #1081):

    The ``downgrade()`` function reverses cleanly:

        1. ALTER TABLE canonical_events DROP CONSTRAINT
           canonical_events_series_id_fkey
        2. ALTER TABLE canonical_events ADD CONSTRAINT
           canonical_events_series_id_fkey FOREIGN KEY (series_id)
           REFERENCES series(id)  -- PG default ON DELETE NO ACTION
        3. Same DROP/ADD pair for canonical_events_game_id_fkey.

    The downgrade restores the prior schema state (NO ACTION default),
    matching the round-trip oracle's pg_get_constraintdef snapshot.  No
    deliberate-imperfection points in this migration's round-trip --
    upgrade and downgrade are byte-symmetric.

Revision ID: 0077
Revises: 0076
Create Date: 2026-04-29

Issue: #1075 (ADR-118 V2.42 sub-amendment B retrofit)
Epic: #972 (Canonical Layer Foundation -- Phase B.5)
ADR: ADR-118 V2.42 sub-amendment B (canonical_events FK ON DELETE SET NULL
    for game_id + series_id)
Council: ``memory/design_review_0076_synthesis.md`` (Holden + Galadriel +
    Miles + Uhura, session 83)
Companion: slot 0076 (#1074 generic ``set_updated_at()`` retrofit + 4-table
    install, V2.42 sub-amendment A) -- shipped same arc, sequenced first
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0077"
down_revision: str = "0076"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# FK constraints retrofitted in slot 0077.  Pattern 73 SSOT canonical home
# for the constraint-name list -- the same names are pinned by the
# integration test (test_migration_0067_canonical_events_foundation.py
# lines 400-450) and the new behavioral test
# (test_migration_0077_fk_on_delete_set_null.py).  Names PRESERVED across
# DROP/ADD per Holden-FK -- PG default-generated names would break the
# pinned-by-name test assertions.
_FK_CONSTRAINTS: tuple[tuple[str, str, str], ...] = (
    # (constraint_name, fk_column, parent_table)
    ("canonical_events_game_id_fkey", "game_id", "games"),
    ("canonical_events_series_id_fkey", "series_id", "series"),
)
"""FK constraints retrofitted from default ON DELETE NO ACTION to
ON DELETE SET NULL in slot 0077.  Both columns are already NULLABLE per
Migration 0067 -- SET NULL is type-compatible without column ALTER."""


def upgrade() -> None:
    """Flip canonical_events.{game_id, series_id} FKs from NO ACTION to SET NULL.

    Sequence (single-phase ALTER per Pattern 84 carve-out -- canonical_events
    is empty):
        1. For each FK in ``_FK_CONSTRAINTS``:
            a. DROP CONSTRAINT (existing default-NO-ACTION constraint).
            b. ADD CONSTRAINT (re-create with explicit ON DELETE SET NULL,
               PRESERVING the original constraint name).

    No NOT VALID + VALIDATE phase -- canonical_events has 0 rows at slot
    0077 deploy time, Pattern 84's "When NOT to Apply" carve-out fires.
    The ALTER acquires AccessExclusiveLock on canonical_events but performs
    no row scan; lock duration is bounded by metadata catalog updates
    (sub-second on empty table).
    """
    # ------------------------------------------------------------------
    # Step 1: Flip both FK constraints' ON DELETE polarity.
    #
    # The DROP CONSTRAINT + ADD CONSTRAINT round-trip is required because
    # PostgreSQL does not support ``ALTER TABLE ... ALTER CONSTRAINT ...
    # ON DELETE`` directly -- only deferrable / not-deferrable can be
    # altered in place; ON DELETE action requires drop-and-recreate.
    #
    # Constraint NAMES are PRESERVED (Holden-FK).  PG default-generated
    # names would break the pinned-by-name test assertions in
    # test_migration_0067 (lines 400-450) and any consumer grepping for
    # the constraint name.
    #
    # ``DROP CONSTRAINT`` (no IF EXISTS) is intentional in upgrade: if
    # either constraint is missing pre-upgrade, schema state has diverged
    # and the upgrade should fail loud -- exactly the loud-failure
    # semantic Holden wants for FK retrofits (vs the silent staleness
    # that motivated SPLIT into 0076 + 0077).
    # ------------------------------------------------------------------
    for constraint_name, fk_column, parent_table in _FK_CONSTRAINTS:
        op.execute(f"ALTER TABLE canonical_events DROP CONSTRAINT {constraint_name}")
        op.execute(
            f"""
            ALTER TABLE canonical_events
                ADD CONSTRAINT {constraint_name}
                FOREIGN KEY ({fk_column})
                REFERENCES {parent_table}(id)
                ON DELETE SET NULL
            """
        )


def downgrade() -> None:
    """Reverse 0077: restore default ON DELETE NO ACTION on both FKs.

    Sequence (mirrors ``upgrade()`` -- DROP CONSTRAINT + ADD CONSTRAINT
    pair, but the re-added constraints OMIT the explicit ON DELETE clause
    so PG defaults to NO ACTION, matching the Migration 0067 pre-retrofit
    state byte-for-byte against the round-trip oracle's
    ``pg_get_constraintdef`` snapshot).

    ``IF EXISTS`` is used on the DROP for idempotent rollback per session
    59 ``feedback_idempotent_migration_drops.md``.  Re-running the
    downgrade on a partially-rolled-back DB is a no-op rather than a
    crash.
    """
    # ------------------------------------------------------------------
    # Step 1: Restore default NO ACTION polarity on both FKs.
    #
    # ADD CONSTRAINT body OMITS the ON DELETE clause -- PG defaults to
    # NO ACTION, which matches the Migration 0067 pre-retrofit state
    # exactly (pg_get_constraintdef does not emit "ON DELETE NO ACTION"
    # because NO ACTION is the default).  The round-trip oracle's
    # snapshot will re-converge to the pre-slot-0077 state.
    # ------------------------------------------------------------------
    for constraint_name, fk_column, parent_table in _FK_CONSTRAINTS:
        op.execute(f"ALTER TABLE canonical_events DROP CONSTRAINT IF EXISTS {constraint_name}")
        op.execute(
            f"""
            ALTER TABLE canonical_events
                ADD CONSTRAINT {constraint_name}
                FOREIGN KEY ({fk_column})
                REFERENCES {parent_table}(id)
            """
        )
