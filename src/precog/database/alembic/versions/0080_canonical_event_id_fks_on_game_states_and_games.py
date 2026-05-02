"""Cohort 4 slot 0080 -- ``game_states`` + ``games`` ``canonical_event_id`` nullable FKs.

Lands the **third Cohort 4 slot**, the first to touch already-populated
production tables (``game_states`` ~41k rows; ``games`` ~5k rows in dev at
build time).  Both tables receive a structurally-identical change: a new
nullable ``BIGINT canonical_event_id`` column with an FK constraint to
``canonical_events(id) ON DELETE SET NULL`` and a per-table index for
matcher reverse-lookup + cascade-fan-out efficiency.

Per session 86 PM-composed build spec at
``memory/build_spec_0080_pm_memo.md`` (binding-and-ready, queued for
session 88 dispatch) + ADR-118 V2.43 Item 2 (Cohort 4 scope lock; slot
0081 retired into 0080 -- single combined slot for both populated tables)
+ ADR-118 V2.42 sub-amendment B (canonical-outlives-platform polarity
convention precedent from slot 0077 -- platform-tier rows like games and
game_states are *outlived* by canonical_events; deleting a canonical
event does not destroy the platform-side row, it nulls the link).

Slot 0080 ships TWO ALTER TABLE rounds (game_states + games), each:

    1. ADD COLUMN canonical_event_id BIGINT (nullable, no default).
    2. ADD CONSTRAINT fk_<table>_canonical_event_id FOREIGN KEY
       (canonical_event_id) REFERENCES canonical_events(id) ON DELETE
       SET NULL NOT VALID -- Pattern 84 by analogy: defer immediate
       validation so we don't acquire ACCESS EXCLUSIVE on canonical_events
       during the validation scan against the populated child table.
    3. VALIDATE CONSTRAINT fk_<table>_canonical_event_id -- acquires only
       SHARE UPDATE EXCLUSIVE on the referencing table; concurrent
       reads/writes on the parent (canonical_events) proceed during the
       scan.  Trivially-pass first run because every existing row has
       canonical_event_id=NULL (just-added column).
    4. CREATE INDEX idx_<table>_canonical_event_id -- supports the
       matcher's "what platform-tier rows are bound to canonical event X"
       reverse lookup AND speeds up the FK's ON DELETE SET NULL cascade
       scan (without it, every parent DELETE does a sequential scan on
       the child).

FK polarity rationale (ADR-118 V2.42 sub-amendment B):

    ON DELETE SET NULL preserves the platform-tier rows when their bound
    canonical_events row is deleted.  Game-state polling continues to
    write rows even after a canonical event is voided/superseded;
    losing platform-tier rows because of a canonical-side delete would
    destroy data that is outside the canonical layer's authority.  The
    matcher (Cohort 5+) re-binds nulled canonical_event_id values when
    a replacement canonical event is created.

Why combined (slot 0081 retired into 0080 per Q5 user adjudication
session 86 + V2.43 Item 2):

    Both tables receive structurally-identical changes (same FK shape,
    same polarity, same index naming convention).  Both are populated
    enough to require Pattern 84 NOT VALID + VALIDATE; neither is so
    large that splitting into two slots would buy meaningful isolation.
    The combined slot keeps the "first Cohort 4 slot touching populated
    tables" risk surface in one PR for council-level scrutiny rather
    than diffusing the same risk across two PRs.

Pattern 73 (SSOT) -- N/A this slot:

    No new vocabulary tuples.  The new column type (BIGINT) and FK
    target (canonical_events.id BIGSERIAL) inherit from the parent
    table's existing schema (Migration 0067).  No CHECK constraints on
    the new column other than the FK shape (which is constraint-level,
    not value-level).  The lifecycle_phase vocabulary semantics live in
    canonical_events, unchanged by slot 0080.

Pattern 81 (lookup convention) -- N/A:

    No new lookup table.  The new column references the existing
    canonical_events surrogate PK, which is already a typed integer
    surrogate -- no value vocabulary to canonicalize via lookup.

Pattern 84 (NOT VALID + VALIDATE on populated tables) -- APPLIED BY ANALOGY:

    Pattern 84 (DEVELOPMENT_PATTERNS V1.38) is canonically about CHECK
    constraints on populated tables.  The technique generalizes cleanly
    to FK constraints: ADD CONSTRAINT ... NOT VALID acquires only a
    short ACCESS EXCLUSIVE lock to record the constraint definition;
    subsequent VALIDATE CONSTRAINT acquires only SHARE UPDATE EXCLUSIVE
    on the referencing table during the scan.  PostgreSQL documentation
    is unambiguous on this; the lock-class semantics for FK NOT VALID +
    VALIDATE are identical to CHECK NOT VALID + VALIDATE.

    Why this slot needs it.  ``game_states`` has ~41k rows and ``games``
    has ~5k rows in dev at build time; production magnitudes are similar
    or larger.  An immediate-validate FK ADD against a populated child
    table briefly takes ACCESS EXCLUSIVE on the *referenced* table
    (canonical_events) during the scan -- that lock blocks concurrent
    reads on canonical_events.  NOT VALID + VALIDATE pattern keeps the
    referenced table available for concurrent ops; only the referencing
    table sees a SHARE UPDATE EXCLUSIVE lock during the scan.

    The validation itself is trivially-pass on this slot's first run
    because every existing row has canonical_event_id=NULL (the column
    was just added).  That makes the VALIDATE step effectively free.
    Future re-runs after backfill (Cohort 5+) will exercise the scan
    against real populated values; using the pattern now means the
    operational shape is stable across runs.

    If S69's next sweep flags this as a Pattern 84 promotion candidate
    (extend Pattern 84 from CHECK to FK explicitly in DEVELOPMENT_PATTERNS),
    that is a reasonable follow-up.  The slot 0080 build correctly applies
    the technique by analogy regardless of whether the pattern doc is
    expanded.

Pattern 87 (Append-only migrations) -- REAFFIRMED CLEAN:

    DEVELOPMENT_PATTERNS V1.40.  Slot 0080 is a NEW migration; Pattern 87
    fires when editing PREVIOUSLY-MERGED migrations.  This PR makes ZERO
    edits to migrations 0001-0079.  No forward-pointer comment is
    inserted into slot 0079's docstring (the existing slot 0079 already
    documents slot 0080 in its scope-fence "What slot 0079 deliberately
    does NOT include" section).

Out of scope (per V2.43 Item 2 + Cohort 4 council carve-outs):

    * NO BACKFILL of canonical_event_id from existing rows.  The matcher
      (Cohort 5+) will populate values as canonical_events rows are
      created and bound.  Slot 0080 leaves all existing rows with
      canonical_event_id=NULL.
    * NO NOT NULL tightening.  Far-future Cohort 6+ work, only after
      backfill confirms 100% coverage AND a soak window AND production
      confirms no orphans.
    * NO application-layer reads/writes of canonical_event_id.  Cohort 5+
      consumers ship as their own slots.
    * NO trigger-side enforcement that canonical_event_id matches
      temporal_alignment view's expected row.  Cohort 5+ matcher shapes
      this.
    * NO view rewires (v_temporal_alignment to use canonical_event_id
      directly).  Slot 0083 territory.
    * NO temporal_alignment.canonical_event_id FK.  Slot 0082 territory.
    * NO new CRUD module.  Pure DDL slot.
    * NO new constants.  No new vocabulary.

Round-trip discipline (PR #1081 round-trip CI gate):

    Slot 0080's downgrade() is a pure inverse of upgrade(): every CREATE
    has a matching DROP IF EXISTS in downgrade.  Drop order respects
    object dependencies (index -> FK constraint -> column).  The
    round-trip gate auto-discovers slot 0080 on push and runs
    downgrade -> upgrade head against it.

    The downgrade is intentionally lossy at the schema-bookkeeping
    level: the new column + FK + index are dropped.  Per the round-trip
    gate's standing banner, downgrade is NOT certified safe to run on a
    populated production DB without a separate backup/restore drill
    (Epic #1071 / #1067); the gate verifies schema reversibility only.

Revision ID: 0080
Revises: 0079
Create Date: 2026-05-02

Issues: Epic #972 (Canonical Layer Foundation -- Phase B.5),
    V2.43 Item 2 (Cohort 4 slot 0080 commitment + slot 0081 retirement),
    V2.42 sub-amendment B (canonical_events FK polarity convention)
ADR: ADR-118 V2.43 Item 2 + V2.42 sub-amendment B
Build spec: ``memory/build_spec_0080_pm_memo.md``
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0080"
down_revision: str = "0079"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add canonical_event_id BIGINT nullable + FK SET NULL + index on game_states + games.

    Step order per table (Pattern 84 by analogy: NOT VALID + VALIDATE for
    populated child tables):

        1. ADD COLUMN canonical_event_id BIGINT (nullable, no default).
        2. ADD CONSTRAINT ... ON DELETE SET NULL NOT VALID.
        3. VALIDATE CONSTRAINT (trivially-pass on first run -- column is
           freshly NULL-filled).
        4. CREATE INDEX (plain, not CONCURRENTLY -- both tables are small
           enough that the brief write-block during index build is
           negligible per build spec § 9 #3 PM adjudication).

    game_states first, then games.  Order is operationally insignificant
    (the two ALTER rounds are independent) but consistent ordering keeps
    the migration + downgrade + tests easier to follow.
    """
    # =========================================================================
    # game_states: ADD COLUMN + ADD CONSTRAINT NOT VALID + VALIDATE + INDEX
    # =========================================================================
    op.execute(
        """
        ALTER TABLE game_states
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
        ALTER TABLE game_states
            ADD CONSTRAINT fk_game_states_canonical_event_id
            FOREIGN KEY (canonical_event_id)
            REFERENCES canonical_events(id)
            ON DELETE SET NULL
            NOT VALID
        """
    )
    # VALIDATE acquires only SHARE UPDATE EXCLUSIVE on game_states; reads
    # + writes on canonical_events proceed concurrently during the scan.
    op.execute(
        """
        ALTER TABLE game_states
            VALIDATE CONSTRAINT fk_game_states_canonical_event_id
        """
    )
    # Index supports (a) matcher reverse-lookup ("which game_states rows
    # are bound to canonical event X?") and (b) the FK's ON DELETE SET
    # NULL cascade scan -- without this index, every canonical_events
    # DELETE forces a sequential scan on game_states to find rows whose
    # canonical_event_id matches the deleted parent.
    op.execute(
        """
        CREATE INDEX idx_game_states_canonical_event_id
            ON game_states (canonical_event_id)
        """
    )

    # =========================================================================
    # games: same shape, repeated (build spec § 2 -- structurally identical)
    # =========================================================================
    op.execute(
        """
        ALTER TABLE games
            ADD COLUMN canonical_event_id BIGINT
        """
    )
    op.execute(
        """
        ALTER TABLE games
            ADD CONSTRAINT fk_games_canonical_event_id
            FOREIGN KEY (canonical_event_id)
            REFERENCES canonical_events(id)
            ON DELETE SET NULL
            NOT VALID
        """
    )
    op.execute(
        """
        ALTER TABLE games
            VALIDATE CONSTRAINT fk_games_canonical_event_id
        """
    )
    op.execute(
        """
        CREATE INDEX idx_games_canonical_event_id
            ON games (canonical_event_id)
        """
    )


def downgrade() -> None:
    """Reverse 0080: drop indexes + FK constraints + columns on both tables.

    Drop order per table (standard PG dependency order):

        1. DROP INDEX -- explicit drop for clarity (DROP COLUMN would
           cascade indexes referencing the column, but explicit DROP
           keeps the downgrade readable and matches slot 0073 / slot
           0076 / slot 0077 / slot 0078 / slot 0079 convention).
        2. DROP CONSTRAINT (FK) -- safe after the index is gone.  PG
           would also cascade this on DROP COLUMN, but explicit ordering
           keeps the inverse mapping audit-friendly.
        3. DROP COLUMN -- leaf; nothing else references the column once
           the FK + index are gone.

    games first, then game_states (reverse of upgrade order).  ``IF
    EXISTS`` used throughout for idempotent rollback per session 59
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
    # games: drop in reverse order (index -> FK -> column)
    # =========================================================================
    op.execute("DROP INDEX IF EXISTS idx_games_canonical_event_id")
    op.execute("ALTER TABLE games DROP CONSTRAINT IF EXISTS fk_games_canonical_event_id")
    op.execute("ALTER TABLE games DROP COLUMN IF EXISTS canonical_event_id")

    # =========================================================================
    # game_states: drop in reverse order (index -> FK -> column)
    # =========================================================================
    op.execute("DROP INDEX IF EXISTS idx_game_states_canonical_event_id")
    op.execute(
        "ALTER TABLE game_states DROP CONSTRAINT IF EXISTS fk_game_states_canonical_event_id"
    )
    op.execute("ALTER TABLE game_states DROP COLUMN IF EXISTS canonical_event_id")
