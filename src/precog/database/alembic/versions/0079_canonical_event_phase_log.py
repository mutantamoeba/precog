"""Cohort 4 slot 0079 -- ``canonical_event_phase_log`` audit ledger + auto-population trigger.

Lands the second canonical-tier audit-ledger table of the schema-hardening
arc (slot 0073's ``canonical_match_log`` was the first; slot 0079 mirrors
that shape for the event-lifecycle dimension).  Every transition of
``canonical_events.lifecycle_phase`` now produces a forever-record row in
``canonical_event_phase_log`` capturing predecessor + successor phase,
the actor (system-trigger or operator), and a free-form note.

Per session-86 V2.43 ADR-118 amendment Item 2 (Cohort 4 scope lock) +
session-87 PM-composed build spec at ``memory/build_spec_0079_pm_memo.md`` +
session-87 S82 SKIP verdict (``memory/s82_slot_0079_skip_memo.md``;
single-table audit ledger mirroring slot 0073 -- not new module / not
major-enrichment).

Slot 0079 ships ONE table, 3 indexes, 2 CHECKs, 1 trigger function, 1
trigger.  The table itself is append-only via application discipline
(slot 0073 inheritance per L10 + Elrond E:90); trigger-level append-only
enforcement is queued for slot 0090 after the same 30-day soak window.

8-value lifecycle_phase vocabulary -- mirrored verbatim from canonical_events.lifecycle_phase:

    'proposed', 'listed', 'pre_event', 'live',
    'suspended', 'settling', 'resolved', 'voided'

Origin: extracted via MCP ``pg_get_constraintdef`` query against
``canonical_events_lifecycle_phase_check`` shipped in Migration 0070
(ADR-118 V2.40 Cohort 1 carry-forward Item 3).  The Pattern 73 SSOT
canonical home is ``src/precog/database/constants.py:CANONICAL_EVENT_LIFECYCLE_PHASES``;
both the ``new_phase`` and ``previous_phase`` CHECKs in this migration
mirror that constant's contents.  Three-way SSOT parity is verified by
``tests/integration/database/test_lifecycle_phase_vocabulary_ssot.py``.

Auto-population trigger (build spec § 2 -- the operationally distinctive
shape of slot 0079 vs. slot 0073's manual-only path):

    ``trg_canonical_events_log_phase_transition`` is an AFTER INSERT OR
    UPDATE OF lifecycle_phase trigger on ``canonical_events`` that fires
    ``log_canonical_event_phase_transition()``.  The function INSERTs a
    row into ``canonical_event_phase_log`` whenever:

        * A new canonical_events row is INSERTed (previous_phase=NULL,
          new_phase=NEW.lifecycle_phase, changed_by='system').
        * An existing canonical_events row is UPDATEd AND the
          ``lifecycle_phase`` column value changes (previous_phase=
          OLD.lifecycle_phase, new_phase=NEW.lifecycle_phase,
          changed_by='system').

    The trigger uses ``IS DISTINCT FROM`` (NULL-safe) rather than ``!=``
    to handle phase transitions where one side might be NULL (e.g., a
    historical pre-CHECK row -- though canonical_events.lifecycle_phase
    is NOT NULL post-Migration 0070 so this is defensive).  The
    ``OF lifecycle_phase`` firing scope means routine UPDATEs that touch
    other columns (e.g., ``title`` UPDATEs that fire the slot-0076
    BEFORE UPDATE ``set_updated_at`` trigger) do NOT generate phase-log
    rows -- only true phase transitions land in the audit stream.

    Trigger ordering with slot 0076 ``set_updated_at`` (build spec § 8 #3):
    PostgreSQL fires BEFORE triggers ahead of AFTER triggers, so
    ``trg_canonical_events_updated_at`` (BEFORE UPDATE) executes first
    and bumps ``updated_at``; then ``trg_canonical_events_log_phase_transition``
    (AFTER UPDATE OF lifecycle_phase) executes and writes the audit row
    if the phase actually changed.  The two triggers are independent;
    neither blocks nor depends on the other.

FK polarity rationale (build spec § 2):

    ``canonical_event_id BIGINT NOT NULL REFERENCES canonical_events(id)
    ON DELETE CASCADE``:

        Audit log entries die with the event they audit.  Differs from
        slot 0073's ``canonical_match_log.link_id ON DELETE SET NULL``
        because ``canonical_event_phase_log`` is *inseparable* from its
        parent event: the event IS the subject (without the event the
        log entry describes nothing), whereas a match-log row's
        ``(platform_market_id, canonical_market_id)`` tuple still anchors
        attribution after a link deletion.  No "audit history outlives
        the parent" semantics here because there is no parallel
        attribution tuple.  DO NOT relax to SET NULL or NO ACTION
        without an ADR amendment + audit-log retention policy review.

Pattern 73 (SSOT) -- reuses existing ``CANONICAL_EVENT_LIFECYCLE_PHASES`` constant:

    The lifecycle_phase 8-value vocabulary lives canonically at
    ``src/precog/database/constants.py:CANONICAL_EVENT_LIFECYCLE_PHASES``,
    pre-positioned by Migration 0070 + V2.40 Cohort 1 carry-forward Item 3.
    Slot 0079 deliberately REUSES that constant rather than introducing a
    sibling ``LIFECYCLE_PHASE_VALUES`` tuple: Pattern 73 SSOT discipline
    says "any rule, value, formula, or logic that appears in more than one
    location MUST have ONE canonical definition plus pointers/imports".
    Build spec § 3 originally proposed ``LIFECYCLE_PHASE_VALUES`` as the
    name; Builder reuses the existing constant per the Pattern itself.
    The build spec named the tuple by the wrong constant -- correctness
    is preserved; vocabulary-home is a single tuple with pointers
    (3 locations: this migration's two CHECKs + canonical_events CHECK
    in Migration 0070).  The ``crud_canonical_event_phase_log`` module
    uses this constant in real-guard ValueError-raising validation
    (#1085 finding #2 strengthening discipline inherited from slot 0073).

Pattern 73 (SSOT) -- DECIDED_BY_PREFIXES reuse for ``changed_by``:

    The 3-prefix actor taxonomy (``human:`` / ``service:`` / ``system:``)
    introduced for slot 0073's ``canonical_match_log.decided_by`` is
    SHAPE-IDENTICAL to slot 0079's ``canonical_event_phase_log.changed_by``.
    Per build spec § 8 #2 + Pattern 73 SSOT, slot 0079 reuses
    ``DECIDED_BY_PREFIXES`` rather than introducing a sibling tuple.

    The trigger-emitted rows use ``changed_by = 'system:trigger'`` (a
    valid prefix-matched value), which preserves the existing 3-prefix
    vocabulary contract -- no extension to DECIDED_BY_PREFIXES is needed.

Pattern 81 (lookup convention) -- N/A carve-out for ``new_phase``/``previous_phase``:

    The 8-value lifecycle_phase vocabulary is intentionally NOT a Pattern
    81 lookup table.  The phase set is closed (every value binds to
    state-machine code branches per Pattern 81 § "When NOT to Apply");
    adding a new phase requires a code deploy regardless of where the
    vocabulary lives.  Same Pattern 81 carve-out shape as slot 0073's
    ``ACTION_VALUES``.  A future "consistency cleanup" PR proposing a
    ``canonical_event_lifecycle_phases`` lookup table should fail design
    review at this docstring level.

Pattern 84 (NOT VALID + VALIDATE for CHECK on populated tables) -- N/A:

    Fresh empty table; ``canonical_event_phase_log`` does not exist
    before this migration.  No seed paths; the first row in the table
    will be written by the auto-population trigger when the first
    canonical_events row gets INSERTed (Cohort 5+ runtime code).  Per
    Pattern 84 § "When NOT to Apply" both criteria met:

        * Zero rows in dev/staging at migration time (table doesn't
          exist yet).
        * No expected rows by production deploy time (no seeds; populated
          by the trigger only when canonical_events itself is populated,
          which is Cohort 5+ matcher pipeline territory).

Pattern 87 (Append-only migrations) -- REAFFIRMED CLEAN:

    DEVELOPMENT_PATTERNS V1.40.  Slot 0079 is a NEW migration; Pattern 87
    fires when editing PREVIOUSLY-MERGED migrations.  This PR makes ZERO
    edits to migrations 0001-0078.  Slot 0078's ``canonical_observations``
    docstring carries a forward-pointer to slot 0079; that forward-pointer
    remains correct as-of this PR (no edit needed).

Append-only via application discipline (slot 0073 inheritance):

    The ledger has NO ``BEFORE INSERT OR UPDATE OR DELETE`` trigger on
    itself.  No ``RAISE EXCEPTION`` on UPDATE / DELETE of the log table.
    Direct UPDATE/DELETE SQL on ``canonical_event_phase_log`` would
    succeed at the DB level.  The discipline is:

        1. ``crud_canonical_event_phase_log.py`` exposes EXACTLY ONE
           write function: ``append_phase_transition()``.
        2. There are NO ``update_*`` / ``delete_*`` / ``upsert_*``
           functions in the CRUD module.
        3. The CRUD module's docstring loudly forbids ad-hoc UPDATE/DELETE
           SQL touching this table.
        4. Code review enforces the discipline; future grep audits (S81)
           sweep for direct ``UPDATE canonical_event_phase_log`` /
           ``DELETE FROM canonical_event_phase_log`` SQL outside this
           migration's downgrade.

    The trigger-enforced version (BEFORE UPDATE/DELETE -> RAISE EXCEPTION)
    is queued for slot 0090 after a 30-day production soak validates the
    application-discipline approach (slot 0073 precedent inheritance).

What slot 0079 deliberately does NOT include (scope fence):

    * No append-only enforcement trigger on the log table itself --
      application-discipline only; trigger retrofit queued for slot 0090
      after 30-day soak (slot 0073 precedent).
    * No ``BEFORE UPDATE`` trigger for ``updated_at`` maintenance --
      append-only tables don't have an ``updated_at`` column at all.
    * No BACKFILL of phase log from existing canonical_events rows --
      canonical_events has 0 rows at production deploy time per slot
      0076 preamble; backfill is a no-op.
    * No per-phase-transition observation emission to
      canonical_observations -- future cohort scope (when reconciler ships).
    * No FK from canonical_event_phase_log to canonical_observations --
      phase changes are audit events; they don't naturally tie to the
      observation stream.
    * No ``update_*`` / ``delete_*`` / ``upsert_*`` CRUD functions; the
      module exposes a single restricted ``append_phase_transition()``
      write path.
    * No seed data -- log table is populated by the trigger when
      canonical_events itself is populated (Cohort 5+).

Round-trip discipline (PR #1081 round-trip CI gate):

    Slot 0079's ``downgrade()`` is a pure inverse of ``upgrade()``: every
    CREATE has a matching ``DROP IF EXISTS`` in downgrade.  Drop order
    respects object dependencies (trigger -> trigger function -> indexes
    -> table).  The round-trip gate auto-discovers slot 0079 on push and
    runs ``downgrade -> upgrade head`` against it.

Revision ID: 0079
Revises: 0078
Create Date: 2026-05-01

Issues: Epic #972 (Canonical Layer Foundation -- Phase B.5),
    V2.43 Item 2 (Cohort 4 slot 0079 commitment),
    V2.40 Cohort 1 carry-forward Item 3 (lifecycle_phase 8-value vocabulary)
ADR: ADR-118 V2.40 Item 3 + V2.43 Item 2
Build spec: ``memory/build_spec_0079_pm_memo.md``
S82 verdict: ``memory/s82_slot_0079_skip_memo.md`` (SKIP per audit-ledger precedent)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0079"
down_revision: str = "0078"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create canonical_event_phase_log + 3 indexes + 2 CHECKs + trigger function + trigger.

    Step order:

        1. ``canonical_event_phase_log`` table (CREATE TABLE with FK clause +
           2 inline CHECK constraints).
        2. ``idx_canonical_event_phase_log_transition_at`` -- audit hot path.
        3. ``idx_canonical_event_phase_log_canonical_event_id`` -- FK target.
        4. ``idx_canonical_event_phase_log_event_transition`` -- composite
           for "phase history of event X newest-first" runbook query.
        5. ``log_canonical_event_phase_transition()`` PL/pgSQL function.
        6. ``trg_canonical_events_log_phase_transition`` trigger on
           ``canonical_events`` AFTER INSERT OR UPDATE OF lifecycle_phase.
    """
    # =========================================================================
    # canonical_event_phase_log
    #
    # Column-level rationale (Builder docstring obligation per build spec § 2):
    #   - id BIGSERIAL PK: surrogate.  No child rows FK INTO this table; the
    #     PK exists for direct-row addressability in operator runbooks.
    #   - canonical_event_id BIGINT NOT NULL ON DELETE CASCADE: audit log
    #     dies with the parent event (no parallel attribution tuple to
    #     anchor orphans, unlike slot 0073's match-log).
    #   - previous_phase VARCHAR(32) NULL: nullable because the first
    #     transition of a canonical_events row has no predecessor (e.g.,
    #     the INSERT path emits NULL -> 'proposed').
    #   - new_phase VARCHAR(32) NOT NULL: every transition has a
    #     destination phase, even the first one.
    #   - transition_at TIMESTAMPTZ NOT NULL DEFAULT now(): when the
    #     phase change occurred; drives the audit-hot-path ORDER BY.
    #   - changed_by VARCHAR(64) NOT NULL: actor attribution.  Pattern 73
    #     SSOT pointer to constants.py:DECIDED_BY_PREFIXES.  The trigger
    #     emits 'system:trigger'; manual operator paths via
    #     append_phase_transition() use 'human:<username>' or other
    #     prefix-matched values.  CHECK does NOT enforce format
    #     (free-text, validated at CRUD boundary).
    #   - note TEXT NULL: free-form operator-readable explanation; no
    #     boundary enforcement (TEXT is unbounded).
    #   - created_at TIMESTAMPTZ NOT NULL DEFAULT now(): ADR-118 V2.42
    #     sub-amendment A canonical convention.  By convention created_at
    #     == transition_at on this table (within microseconds for the
    #     standard trigger and CRUD write paths).
    #
    # NO updated_at column -- this table is append-only; rows are write-once
    # so updated_at would be meaningless.
    # =========================================================================
    op.execute(
        """
        CREATE TABLE canonical_event_phase_log (
            id                    BIGSERIAL    PRIMARY KEY,
            -- canonical_event_id ON DELETE CASCADE: audit log dies with the
            -- parent event (slot 0079 build spec § 2 inline rationale).
            canonical_event_id    BIGINT       NOT NULL REFERENCES canonical_events(id) ON DELETE CASCADE,
            -- previous_phase nullable: first transition of a canonical_events
            -- row has no predecessor (INSERT path emits NULL -> phase).
            previous_phase        VARCHAR(32)  NULL,
            -- new_phase always populated; every transition has a destination.
            new_phase             VARCHAR(32)  NOT NULL,
            -- transition_at is the canonical decision timestamp; drives the
            -- audit-hot-path ORDER BY in operator runbooks.
            transition_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
            -- changed_by Pattern 73 SSOT pointer to constants.py
            -- DECIDED_BY_PREFIXES; CHECK does NOT enforce format
            -- (free-text actor field; CRUD-layer validation in
            -- append_phase_transition() is the discipline).
            changed_by            VARCHAR(64)  NOT NULL,
            note                  TEXT         NULL,
            created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),

            -- 8-value lifecycle_phase vocabulary canonical home:
            -- src/precog/database/constants.py CANONICAL_EVENT_LIFECYCLE_PHASES.
            -- Pattern 73 SSOT: same 8 values appear in canonical_events.lifecycle_phase
            -- CHECK (Migration 0070).  Adding a value requires lockstep update
            -- across (a) the constant, (b) Migration 0070's CHECK, and (c) BOTH
            -- of these CHECKs.  Three-way parity verified by
            -- tests/integration/database/test_lifecycle_phase_vocabulary_ssot.py.
            CONSTRAINT ck_canonical_event_phase_log_new_phase CHECK (
                new_phase IN (
                    'proposed', 'listed', 'pre_event', 'live',
                    'suspended', 'settling', 'resolved', 'voided'
                )
            ),
            CONSTRAINT ck_canonical_event_phase_log_previous_phase CHECK (
                previous_phase IS NULL OR previous_phase IN (
                    'proposed', 'listed', 'pre_event', 'live',
                    'suspended', 'settling', 'resolved', 'voided'
                )
            )
        )
        """
    )

    # Audit hot-path index: ORDER BY transition_at DESC dominates operator
    # runbook queries.  DESC index avoids server-side reverse-scan when
    # paired with ORDER BY transition_at DESC.
    op.execute(
        "CREATE INDEX idx_canonical_event_phase_log_transition_at "
        "ON canonical_event_phase_log (transition_at DESC)"
    )

    # FK-target index on canonical_event_id: supports the "phase history
    # for event X" lookup + speeds up CASCADE delete fan-out.
    op.execute(
        "CREATE INDEX idx_canonical_event_phase_log_canonical_event_id "
        "ON canonical_event_phase_log (canonical_event_id)"
    )

    # Composite index for the canonical operator runbook query:
    # "show me phase history for event X, newest first."  PG can use this
    # index for both the WHERE filter and the ORDER BY in a single scan.
    op.execute(
        "CREATE INDEX idx_canonical_event_phase_log_event_transition "
        "ON canonical_event_phase_log (canonical_event_id, transition_at DESC)"
    )

    # =========================================================================
    # log_canonical_event_phase_transition() -- the trigger function
    #
    # Body discipline:
    #   - INSERT path (TG_OP = 'INSERT'): emit NULL -> NEW.lifecycle_phase
    #     row.  Always fires on canonical_events INSERT; the trigger
    #     declaration restricts UPDATE firing to OF lifecycle_phase, but
    #     INSERT fires unconditionally per PostgreSQL trigger semantics.
    #   - UPDATE path (TG_OP = 'UPDATE'): use IS DISTINCT FROM (NULL-safe)
    #     to handle defensive cases where one side might be NULL.  Even
    #     though canonical_events.lifecycle_phase is NOT NULL post-Migration
    #     0070, IS DISTINCT FROM is the correct idiom for phase-comparison
    #     in trigger functions because it (a) handles NULL on either side
    #     gracefully and (b) the function would still be correct if the
    #     column ever became nullable.
    #   - changed_by='system:trigger' uses the system: prefix from
    #     DECIDED_BY_PREFIXES; satisfies the prefix discipline without
    #     extending the constant.
    #   - The trigger is AFTER (not BEFORE) so the row update is
    #     guaranteed-committed-locally before the audit row is inserted;
    #     prevents the rare "audit log says X happened but the row update
    #     itself rolled back" anomaly that BEFORE triggers can introduce.
    #
    # WARNING: function body whitespace is load-bearing for the PR #1081
    # round-trip CI gate, which snapshots pg_get_functiondef() output.
    # Reformatting the heredoc indentation will break the snapshot oracle
    # even though the function behaves identically.  See slot 0076 P2
    # finding for precedent.
    # =========================================================================
    op.execute(
        """
        CREATE FUNCTION log_canonical_event_phase_transition()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO canonical_event_phase_log (
                    canonical_event_id, previous_phase, new_phase, changed_by, note
                ) VALUES (
                    NEW.id, NULL, NEW.lifecycle_phase, 'system:trigger',
                    'auto-populated from canonical_events INSERT'
                );
            ELSIF TG_OP = 'UPDATE' AND OLD.lifecycle_phase IS DISTINCT FROM NEW.lifecycle_phase THEN
                INSERT INTO canonical_event_phase_log (
                    canonical_event_id, previous_phase, new_phase, changed_by, note
                ) VALUES (
                    NEW.id, OLD.lifecycle_phase, NEW.lifecycle_phase, 'system:trigger',
                    'auto-populated from canonical_events UPDATE'
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    # COMMENT ON FUNCTION documents the trigger's contract for operators
    # inspecting via \df+ log_canonical_event_phase_transition.
    op.execute(
        """
        COMMENT ON FUNCTION log_canonical_event_phase_transition() IS
        'Auto-populates canonical_event_phase_log from canonical_events '
        'INSERT (NULL->phase) and UPDATE OF lifecycle_phase (old->new) '
        'using IS DISTINCT FROM (NULL-safe).  Emits changed_by=''system:trigger''.'
        """
    )

    # =========================================================================
    # trg_canonical_events_log_phase_transition -- AFTER INSERT OR UPDATE OF
    #
    # Firing scope:
    #   - AFTER INSERT: every canonical_events INSERT generates an initial
    #     audit row (NULL -> NEW.lifecycle_phase).
    #   - AFTER UPDATE OF lifecycle_phase: only column-targeted UPDATEs that
    #     touch lifecycle_phase invoke the function; UPDATEs that touch
    #     other columns (e.g., title, updated_at) do NOT fire this trigger.
    #     This is the operationally-distinctive shape: routine UPDATEs that
    #     fire the slot-0076 BEFORE UPDATE set_updated_at trigger do NOT
    #     produce phase-log rows -- only true phase transitions land in
    #     the audit stream.
    #
    # Trigger ordering with slot 0076 trg_canonical_events_updated_at:
    #   PostgreSQL fires BEFORE triggers ahead of AFTER triggers.  The
    #   slot-0076 BEFORE UPDATE trigger sets NEW.updated_at = now(); then
    #   PG performs the UPDATE; then this AFTER trigger fires (only if
    #   lifecycle_phase actually changed).  Independent triggers; no
    #   conflict.  Build spec § 8 #3 verified.
    # =========================================================================
    op.execute(
        """
        CREATE TRIGGER trg_canonical_events_log_phase_transition
            AFTER INSERT OR UPDATE OF lifecycle_phase ON canonical_events
            FOR EACH ROW
            EXECUTE FUNCTION log_canonical_event_phase_transition()
        """
    )


def downgrade() -> None:
    """Reverse 0079: drop trigger + function + 3 indexes + table.

    Drop order:

        1. ``trg_canonical_events_log_phase_transition`` -- drop first;
           the function below depends on it being unwired.
        2. ``log_canonical_event_phase_transition()`` -- safe after the
           trigger is dropped.  NOT CASCADE (no surprises).
        3. Indexes -- explicit drop for clarity (DROP TABLE would cascade
           them, but explicit DROP keeps the downgrade readable and
           matches slot 0073 / slot 0076 convention).
        4. ``canonical_event_phase_log`` table -- leaf; no child tables
           FK INTO this table.

    ``IF EXISTS`` used throughout for idempotent rollback per session 59
    ``feedback_idempotent_migration_drops.md``.  Re-running the downgrade
    on a partially-rolled-back DB is a no-op rather than a crash.

    The downgrade is intentionally lossy: the audit ledger contents are
    discarded.  This is by design; upgrade-then-downgrade-then-upgrade is
    the supported cycle (round-trip CI gate per PR #1081), not downgrade-
    and-keep-running on a populated production DB.
    """
    # Step 1: drop trigger (frees the function for safe DROP).
    op.execute(
        "DROP TRIGGER IF EXISTS trg_canonical_events_log_phase_transition ON canonical_events"
    )

    # Step 2: drop trigger function (NOT CASCADE per slot-0076 precedent).
    op.execute("DROP FUNCTION IF EXISTS log_canonical_event_phase_transition()")

    # Step 3: indexes first (explicit drop for parity with slot 0073 convention).
    op.execute("DROP INDEX IF EXISTS idx_canonical_event_phase_log_event_transition")
    op.execute("DROP INDEX IF EXISTS idx_canonical_event_phase_log_canonical_event_id")
    op.execute("DROP INDEX IF EXISTS idx_canonical_event_phase_log_transition_at")

    # Step 4: leaf table -- no children FK INTO it at slot 0079, so unconditional drop.
    op.execute("DROP TABLE IF EXISTS canonical_event_phase_log")
