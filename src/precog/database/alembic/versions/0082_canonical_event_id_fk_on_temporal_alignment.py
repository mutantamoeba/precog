"""Cohort 4 slot 0082 -- ``temporal_alignment`` ``canonical_event_id`` nullable FK.

Lands the **fourth Cohort 4 slot**, the second to touch an already-populated
production table after slot 0080 (``temporal_alignment`` is the joined view
of canonical events with raw observations -- continuously growing under
production load).  ``temporal_alignment`` receives a structurally-identical
change to slot 0080's two retrofits: a new nullable ``BIGINT
canonical_event_id`` column with an FK constraint to
``canonical_events(id) ON DELETE SET NULL`` and an index on the new column
for matcher reverse-lookup + cascade-fan-out efficiency.

Per session 88 PM-composed build spec at
``memory/build_spec_0082_pm_memo.md`` (binding-and-ready, dispatched
session 88 post-slot-0080-merge) + ADR-118 V2.43 Item 2 (Cohort 4 scope
lock; slot 0082 commitment as separate slot from slot 0080 because
``temporal_alignment`` has its own population characteristics that warrant
clean isolation if the migration encounters unexpected behavior) +
ADR-118 V2.42 sub-amendment B (canonical-outlives-platform polarity
convention; deleting a canonical event nulls the link rather than
destroying the platform-tier observation row).

Slot 0082 ships ONE ALTER TABLE round on ``temporal_alignment``:

    1. ADD COLUMN canonical_event_id BIGINT (nullable, no default).
    2. ADD CONSTRAINT fk_temporal_alignment_canonical_event_id FOREIGN
       KEY (canonical_event_id) REFERENCES canonical_events(id) ON DELETE
       SET NULL NOT VALID -- Pattern 84 by analogy: defer immediate
       validation so we don't acquire ACCESS EXCLUSIVE on canonical_events
       during the validation scan against the populated child table.
    3. VALIDATE CONSTRAINT fk_temporal_alignment_canonical_event_id --
       acquires only SHARE UPDATE EXCLUSIVE on the referencing table;
       concurrent reads/writes on the parent (canonical_events) proceed
       during the scan.  Trivially-pass first run because every existing
       row has canonical_event_id=NULL (just-added column).
    4. CREATE INDEX idx_temporal_alignment_canonical_event_id -- supports
       the matcher's "what temporal_alignment rows are bound to canonical
       event X" reverse lookup AND speeds up the FK's ON DELETE SET NULL
       cascade scan (without it, every parent DELETE does a sequential
       scan on the child).

FK polarity rationale (ADR-118 V2.42 sub-amendment B):

    ON DELETE SET NULL preserves the temporal_alignment rows when their
    bound canonical_events row is deleted.  Temporal alignment is a
    materialized join of market snapshots with game state observations;
    losing those rows because of a canonical-side delete would destroy
    data that is outside the canonical layer's authority.  The matcher
    (Cohort 5+) re-binds nulled canonical_event_id values when a
    replacement canonical event is created.

Why single-table (per V2.43 Item 2):

    Slot 0080 combined ``game_states`` + ``games`` because they are
    structurally-identical platform-tier rows, both small (~41k + ~5k
    rows in dev) and population-stable.  ``temporal_alignment`` has its
    own population characteristics (joins multiple sources; continuously
    grows under production load) and warrants a dedicated slot for clean
    isolation.  If the migration encounters unexpected behavior on
    temporal_alignment, the smaller slot keeps the blast radius
    contained vs bundled with the platform-tier retrofits.

Pattern 73 (SSOT) -- N/A this slot:

    No new vocabulary tuples.  The new column type (BIGINT) and FK
    target (canonical_events.id BIGSERIAL) inherit from the parent
    table's existing schema (Migration 0067).  No CHECK constraints on
    the new column other than the FK shape (which is constraint-level,
    not value-level).  The lifecycle_phase vocabulary semantics live in
    canonical_events, unchanged by slot 0082.

Pattern 81 (lookup convention) -- N/A:

    No new lookup table.  The new column references the existing
    canonical_events surrogate PK, which is already a typed integer
    surrogate -- no value vocabulary to canonicalize via lookup.

Pattern 84 (NOT VALID + VALIDATE on populated tables) -- APPLIED BY ANALOGY (2nd use):

    Pattern 84 (DEVELOPMENT_PATTERNS V1.38) is canonically about CHECK
    constraints on populated tables.  Slot 0080 established the by-analogy
    precedent for FK constraints (with explicit reviewer + sentinel
    sign-off); slot 0082 is the **second** by-analogy use, exactly the
    threshold (N>=2) the spec § 8 cites for a future S69 sweep to flag
    Pattern 84 promotion to explicitly cover FK constraints in
    DEVELOPMENT_PATTERNS V1.42+.  The technique generalizes cleanly: ADD
    CONSTRAINT ... NOT VALID acquires only a short ACCESS EXCLUSIVE lock
    to record the constraint definition; subsequent VALIDATE CONSTRAINT
    acquires only SHARE UPDATE EXCLUSIVE on the referencing table during
    the scan.

    Why this slot needs it.  ``temporal_alignment`` is the largest of the
    Cohort 4 FK-retrofit targets in the long run -- it joins market
    snapshots (every ~15s) with game state observations and grows
    continuously under production load.  Dev-DB row count at build time
    was 0 (per build-spec § 9 #3 MCP verification on session 88), so
    plain CREATE INDEX is correct for this run; production magnitudes
    will be larger but the operational shape (NOT VALID + VALIDATE) is
    stable across runs.  An immediate-validate FK ADD against a populated
    child table briefly takes ACCESS EXCLUSIVE on the *referenced* table
    (canonical_events) during the scan -- that lock blocks concurrent
    reads on canonical_events.  NOT VALID + VALIDATE pattern keeps the
    referenced table available for concurrent ops; only the referencing
    table sees a SHARE UPDATE EXCLUSIVE lock during the scan.

    The validation itself is trivially-pass on this slot's first run
    because every existing row has canonical_event_id=NULL (the column
    was just added).  Future re-runs after backfill (Cohort 5+) will
    exercise the scan against real populated values; using the pattern
    now means the operational shape is stable across runs.

Pattern 87 (Append-only migrations) -- REAFFIRMED CLEAN:

    DEVELOPMENT_PATTERNS V1.40.  Slot 0082 is a NEW migration; Pattern 87
    fires when editing PREVIOUSLY-MERGED migrations.  This PR makes ZERO
    edits to migrations 0001-0080.  No forward-pointer comment is
    inserted into slot 0080's docstring (the existing slot 0080 already
    documents slot 0082 in its scope-fence "What slot 0080 deliberately
    does NOT include" section: ``NO temporal_alignment.canonical_event_id
    FK.  Slot 0082 territory.``).

Note on alembic chain (non-monotonic chain):

    At session-88-post-slot-0080-merge, the alembic head is 0080.  Slot
    0081 was retired into 0080 per V2.43 Item 2 / Q5 user adjudication
    session 86, so slot 0082 builds on 0080 directly: ``down_revision =
    "0080"``.  There is NO migration 0081 in the chain -- this is
    intentional and matches slot 0079's non-monotonic-chain documentation
    precedent (slot 0079's down_revision = "0073" because slot 0074 was
    sequenced after 0079 in chain-order despite the slot-numbering arc).

Index timing decision (build spec § 9 #3):

    MCP verification at build time:
        SELECT count(*), pg_size_pretty(pg_total_relation_size('temporal_alignment'))
        => row_count=0, table_size=56 kB

    Per build-spec decision rule: < 100K rows => plain ``CREATE INDEX``.
    Plain CREATE INDEX takes a brief ACCESS EXCLUSIVE on the referencing
    table during the scan; on a 0-row / 56 kB table the scan is
    microseconds.  CREATE INDEX CONCURRENTLY would be required on a
    > 100K row table (slower, doesn't block writes; but Alembic's default
    transactional handling needs ``op.execute("COMMIT; CREATE INDEX
    CONCURRENTLY ...")``-style hoops to escape the migration's wrapping
    transaction).  Not needed at this size.

Out of scope (per V2.43 Item 2 + Cohort 4 council carve-outs):

    * NO BACKFILL of canonical_event_id from existing rows.  The matcher
      (Cohort 5+) will populate values as canonical_events rows are
      created and bound.  Slot 0082 leaves all existing rows with
      canonical_event_id=NULL.
    * NO NOT NULL tightening.  Far-future Cohort 6+ work, only after
      backfill confirms 100% coverage AND a soak window AND production
      confirms no orphans.
    * NO application-layer reads/writes of canonical_event_id.  Cohort 5+
      consumers ship as their own slots.  The existing
      ``temporal_alignment_writer`` does NOT need modification this slot
      -- the new column is nullable with no default, so existing writes
      succeed without touching it (verified via non-regression
      integration test).
    * NO trigger-side enforcement that canonical_event_id matches the
      view's expected row.  Cohort 5+ matcher shapes this.
    * NO view rewires (v_temporal_alignment to use canonical_event_id
      directly).  Slot 0083 territory.
    * NO new CRUD module.  Pure DDL slot.
    * NO new constants.  No new vocabulary.

Round-trip discipline (PR #1081 round-trip CI gate):

    Slot 0082's downgrade() is a pure inverse of upgrade(): every CREATE
    has a matching DROP IF EXISTS in downgrade.  Drop order respects
    object dependencies (index -> FK constraint -> column).  The
    round-trip gate auto-discovers slot 0082 on push and runs
    downgrade -> upgrade head against it.

    The downgrade is intentionally lossy at the schema-bookkeeping
    level: the new column + FK + index are dropped.  Per the round-trip
    gate's standing banner, downgrade is NOT certified safe to run on a
    populated production DB without a separate backup/restore drill
    (Epic #1071 / #1067); the gate verifies schema reversibility only.

Revision ID: 0082
Revises: 0080
Create Date: 2026-05-02

Issues: Epic #972 (Canonical Layer Foundation -- Phase B.5),
    V2.43 Item 2 (Cohort 4 slot 0082 commitment),
    V2.42 sub-amendment B (canonical_events FK polarity convention)
ADR: ADR-118 V2.43 Item 2 + V2.42 sub-amendment B
Build spec: ``memory/build_spec_0082_pm_memo.md``
Precedent: ``src/precog/database/alembic/versions/0080_canonical_event_id_fks_on_game_states_and_games.py``
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0082"
down_revision: str = "0080"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add canonical_event_id BIGINT nullable + FK SET NULL + index on temporal_alignment.

    Step order (Pattern 84 by analogy: NOT VALID + VALIDATE for populated
    child tables):

        1. ADD COLUMN canonical_event_id BIGINT (nullable, no default).
        2. ADD CONSTRAINT ... ON DELETE SET NULL NOT VALID.
        3. VALIDATE CONSTRAINT (trivially-pass on first run -- column is
           freshly NULL-filled).
        4. CREATE INDEX (plain, not CONCURRENTLY -- table is 0 rows /
           56 kB at build time per build spec § 9 #3 PM adjudication;
           well under the 100K-row threshold for CONCURRENTLY).

    Single-table version of slot 0080's two-table retrofit.  Same Pattern
    84 by-analogy shape.
    """
    # =========================================================================
    # temporal_alignment: ADD COLUMN + ADD CONSTRAINT NOT VALID + VALIDATE + INDEX
    # =========================================================================
    op.execute(
        """
        ALTER TABLE temporal_alignment
            ADD COLUMN canonical_event_id BIGINT
        """
    )
    # Pattern 84 by analogy (FK on populated table): NOT VALID defers the
    # validation scan; the constraint definition is recorded immediately
    # but new rows are checked at INSERT/UPDATE time.  Because the column
    # was just added with NULL for every existing row, the deferred scan
    # is trivially-pass.  The pattern matters operationally: it isolates
    # the brief ACCESS EXCLUSIVE on canonical_events (referenced table)
    # to the constraint-definition step, NOT the (longer) row-scan step.
    op.execute(
        """
        ALTER TABLE temporal_alignment
            ADD CONSTRAINT fk_temporal_alignment_canonical_event_id
            FOREIGN KEY (canonical_event_id)
            REFERENCES canonical_events(id)
            ON DELETE SET NULL
            NOT VALID
        """
    )
    # VALIDATE acquires only SHARE UPDATE EXCLUSIVE on temporal_alignment;
    # reads + writes on canonical_events proceed concurrently during the
    # scan.
    op.execute(
        """
        ALTER TABLE temporal_alignment
            VALIDATE CONSTRAINT fk_temporal_alignment_canonical_event_id
        """
    )
    # Index supports (a) matcher reverse-lookup ("which temporal_alignment
    # rows are bound to canonical event X?") and (b) the FK's ON DELETE
    # SET NULL cascade scan -- without this index, every canonical_events
    # DELETE forces a sequential scan on temporal_alignment to find rows
    # whose canonical_event_id matches the deleted parent.
    op.execute(
        """
        CREATE INDEX idx_temporal_alignment_canonical_event_id
            ON temporal_alignment (canonical_event_id)
        """
    )


def downgrade() -> None:
    """Reverse 0082: drop index + FK constraint + column on temporal_alignment.

    Drop order (standard PG dependency order):

        1. DROP INDEX -- explicit drop for clarity (DROP COLUMN would
           cascade indexes referencing the column, but explicit DROP
           keeps the downgrade readable and matches slot 0073 / slot
           0076 / slot 0077 / slot 0078 / slot 0079 / slot 0080
           convention).
        2. DROP CONSTRAINT (FK) -- safe after the index is gone.  PG
           would also cascade this on DROP COLUMN, but explicit ordering
           keeps the inverse mapping audit-friendly.
        3. DROP COLUMN -- leaf; nothing else references the column once
           the FK + index are gone.

    ``IF EXISTS`` used throughout for idempotent rollback per session 59
    feedback_idempotent_migration_drops.md; re-running the downgrade on
    a partially-rolled-back DB is a no-op rather than a crash.

    The downgrade is intentionally lossy at the schema-bookkeeping
    level: any canonical_event_id values populated by future backfill
    (Cohort 5+) would be lost.  Per the round-trip CI gate's standing
    banner, downgrade is NOT certified safe to run on a populated
    production DB without a separate backup/restore drill (Epic #1071);
    the gate verifies schema reversibility only.
    """
    # =========================================================================
    # temporal_alignment: drop in reverse order (index -> FK -> column)
    # =========================================================================
    op.execute("DROP INDEX IF EXISTS idx_temporal_alignment_canonical_event_id")
    op.execute(
        "ALTER TABLE temporal_alignment "
        "DROP CONSTRAINT IF EXISTS fk_temporal_alignment_canonical_event_id"
    )
    op.execute("ALTER TABLE temporal_alignment DROP COLUMN IF EXISTS canonical_event_id")
