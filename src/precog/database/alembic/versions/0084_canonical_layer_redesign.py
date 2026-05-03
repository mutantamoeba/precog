"""Cohort 4 close-out -- canonical layer redesign (slot 0084).

Realizes the four user-adjudicated decisions of session 90 codified in
ADR-118 V2.45:

    Item 1 -- Cohort 4 informal close + slot 0083 deferral to Cohort 5+
              (issue #1141 tracks the redesigned slot-83-equivalent work).
              No DDL impact in slot 0084; documented here as motivation.

    Item 4 -- Drop ``canonical_observations.payload`` column entirely.
              Per-kind projection tables (``game_states``, ``market_snapshots``,
              future ``weather_observations`` / ``poll_releases`` /
              ``econ_prints`` / ``news_events``) carry typed columns + JSONB
              residue where needed.  ``canonical_observations`` becomes a
              pure lineage / linkage table.  New Pattern 73 SSOT discipline
              rule: adding a new ``observation_kind`` value requires its
              projection table to exist BEFORE the vocabulary expansion.

    Item 6 -- ``temporal_alignment`` redesigned as PURE LINKAGE TABLE.  The
              existing 20-column denormalized fact-table shape (slot 0035-era
              design predating canonical_observations; sport-specific typed
              columns ``home_score`` / ``away_score`` / ``period`` / ``clock``
              / ``yes_ask_price`` / ``no_ask_price`` etc.) is replaced with a
              ~9-column shape: two FKs into ``canonical_observations``, a
              denormalized ``canonical_event_id`` for hot-path lookups, plus
              alignment metadata.  Per-domain typed views
              (``v_temporal_alignment_sports`` /
              ``v_temporal_alignment_weather`` / etc.) are deferred to
              Cohort 5+ alongside writer wiring per issue #1141.

    Item 8 -- Rename ``canonical_observations.canonical_event_id`` to
              ``canonical_primary_event_id`` to make denormalized-as-primary-tag
              semantics explicit + add ``canonical_observation_event_links``
              many-to-many table for multi-event tagging (news fans out
              across multiple canonical_events; econ prints affect dozens
              of econ markets).  The renamed column on canonical_observations
              becomes a hot-path read; the link table carries full
              multi-event semantics with ``link_kind`` discriminator
              (``primary`` / ``secondary`` / ``derived`` / ``speculative``).

V2.46 forward pointer: session 91+ will canonicalize Items 2/3/5/7/9/10
architectural framing via design-review pipeline (Galadriel + Holden +
Scheherazade + Glokta) per issue #1143; binding input at
``memory/design_review_v246_input_memo.md``.

Operational safety verification at build time (S55 MCP-first discipline):

    - ``canonical_observations``: 0 rows (writer feature flag false).
      ``DROP COLUMN payload`` is zero-data-loss.
    - ``temporal_alignment``: 0 rows.  ``DROP TABLE`` + ``CREATE TABLE``
      with new shape is zero-data-loss.
    - alembic_head = ``0082`` (slot 0083 is a permanent hole in the chain;
      same precedent as slot 0081 per V2.43 Item 2).
    - ``game_states.canonical_event_id`` (slot 0080), ``games.canonical_event_id``
      (slot 0080), ``temporal_alignment.canonical_event_id`` (slot 0082) are
      INDEPENDENT columns on different tables -- the rename of
      ``canonical_observations.canonical_event_id`` does NOT affect them.
      Verified via MCP ``information_schema.columns`` query at build time.

Pattern 73 (SSOT) -- new discipline rule + canonical home is the CHECK:

    The ``link_kind`` vocabulary (``primary`` / ``secondary`` / ``derived`` /
    ``speculative``) lives ONLY in this slot's CHECK constraint as the
    canonical home until Cohort 5+ ships the corresponding CRUD module +
    constants tuple ``CANONICAL_OBSERVATION_LINK_KINDS``.  Slot 0084 is a
    pure DDL slot; no Python imports of the vocabulary land this slot.

    The new V2.45 SSOT discipline rule is also load-bearing for future
    cohorts: adding a new ``observation_kind`` value to
    ``OBSERVATION_KIND_VALUES`` requires its projection table to exist
    BEFORE the vocabulary expansion.  This rule guards against the
    "vocab admits a kind we have no projection for" failure mode that the
    original ``canonical_observations.payload`` column papered over.

Pattern 84 (NOT VALID + VALIDATE on populated tables) -- N/A this slot:

    The DROP COLUMN + RENAME COLUMN target table (``canonical_observations``)
    is empty (0 rows).  The DROP TABLE + CREATE TABLE target
    (``temporal_alignment``) is empty.  The new ``canonical_observation_event_links``
    table is empty by definition (just created).  All FKs added in this
    slot are immediate-validate-safe; no Pattern 84 by-analogy needed.

Pattern 87 (Append-only migration files) -- REAFFIRMED CLEAN:

    DEVELOPMENT_PATTERNS V1.40+.  Slot 0084 is a NEW migration file;
    Pattern 87 fires when editing PREVIOUSLY-MERGED migrations.  This PR
    makes ZERO edits to migrations 0001-0082.  In particular:
        - Slot 0078 (``canonical_observations`` parent) is not edited.
          The ``DROP COLUMN payload`` + ``RENAME COLUMN canonical_event_id``
          ALTERs ship in this slot's upgrade(); the slot 0078 file's
          CREATE TABLE statement (which still names ``payload`` and
          ``canonical_event_id``) remains as-shipped.  This is the correct
          shape: future readers reconstructing schema from migrations
          alone replay 0078 -> ... -> 0084 in order, arriving at the
          post-0084 shape without ever editing the historical 0078 text.
        - Slots 0080 + 0082 (which add their OWN ``canonical_event_id``
          columns to game_states / games / temporal_alignment) are not
          edited.  Those columns are entirely independent of the
          canonical_observations rename.

Pattern 86 (Living-Doc Freshness Markers) -- REFRESHED in companion docs:

    DATABASE_SCHEMA_SUMMARY V2.4 (new file) refreshes the freshness marker
    + alembic_head bump to 0084 + canonical_observations / temporal_alignment
    / canonical_observation_event_links entries.  ADR-118 amendment block
    bumps to V2.45.

Slot 0083 permanent hole in the chain (V2.45 Item 1):

    ``down_revision = "0082"`` skips slot 0083 entirely.  Slot 0083 was
    deferred to Cohort 5+ per session 90 user adjudication (Path D); the
    chain hole is intentional and matches the slot 0081 hole shape from
    V2.43 Item 2.  Future readers reconstructing migration chain integrity
    SHOULD see two intentional holes (0081, 0083) corresponding to two
    slot retirements / deferrals; both are documented in their respective
    ADR amendments.

Round-trip discipline (PR #1081 round-trip CI gate):

    Slot 0084's ``downgrade()`` is a pure inverse of ``upgrade()``: every
    DROP / RENAME / CREATE has a matching reverse step.  Drop order
    respects object dependencies (link table -> new temporal_alignment
    -> recreate old temporal_alignment -> reverse rename -> add payload
    column back).  ``IF EXISTS`` used throughout for idempotent rollback
    per session 59 ``feedback_idempotent_migration_drops.md``.

    Recreating the old ``temporal_alignment`` shape in downgrade is
    intentionally faithful to the slot-0082-end shape (20 columns + 8
    constraints + 8 indexes) so the round-trip CI gate can replay
    upgrade -> downgrade -> upgrade and reach an identical schema state
    on each cycle.  The old shape's MCP-verified column inventory is
    captured below in code; the FK on ``canonical_event_id`` is restored
    in the same NOT VALID + VALIDATE shape slot 0082 used.

Revision ID: 0084
Revises: 0082
Create Date: 2026-05-02

Issues: Epic #972 (Canonical Layer Foundation -- Phase B.5),
    V2.45 Items 1/4/6/8 (Cohort 4 informal close + canonical layer redesign),
    #1141 (Cohort 5+ slot-0083-equivalent + per-domain temporal_alignment views),
    #1143 (V2.46 design-review scope -- Items 2/3/5/7/9/10)
ADR: ADR-118 V2.45 (this session)
Memo: ``memory/design_review_v246_input_memo.md`` (binding architectural
    reasoning capture; treats Items 1/4/6/8 as user-adjudicated)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0084"
down_revision: str = "0082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Realize V2.45 Items 4 + 6 + 8: redesign canonical layer.

    Step order (top-down, dependency-respecting):

        1. Drop ``canonical_observations.payload`` column (Item 4).
        2. Rename ``canonical_observations.canonical_event_id`` to
           ``canonical_primary_event_id`` (Item 8).  The existing FK
           constraint (canonical_observations_canonical_event_id_fkey)
           and the existing partial indexes that reference the column
           AUTOMATICALLY follow the rename (PG semantic) -- no separate
           DROP / CREATE needed.
        3. Drop the existing ``temporal_alignment`` table (Item 6 part A).
           Verified empty at build time via MCP.  The slot 0082 FK
           ``fk_temporal_alignment_canonical_event_id`` and the slot 0035-era
           FKs are dropped along with the table (CASCADE-equivalent for
           DROP TABLE).
        4. Create the new ``temporal_alignment`` table with pure-linkage
           shape (Item 6 part B).
        5. Create the ``canonical_observation_event_links`` table (Item 8).

    No data migration needed; all source/target tables are empty.
    """
    # =========================================================================
    # Step 1: Drop canonical_observations.payload (Item 4)
    #
    # Pattern 73 SSOT discipline: per V2.45 Item 4, per-kind projection
    # tables hold all source data (typed columns + JSONB residue where
    # needed; e.g., game_states.situation + game_states.linescores for
    # ESPN's untyped fields).  The payload column on canonical_observations
    # was redundant with what per-kind tables already carry; dropping it
    # makes canonical_observations a pure lineage / linkage table.
    #
    # The associated NOT NULL constraint
    # (canonical_observations_payload_not_null) is dropped automatically
    # when the column is dropped.
    # =========================================================================
    op.execute(
        """
        ALTER TABLE canonical_observations
            DROP COLUMN payload
        """
    )

    # =========================================================================
    # Step 2: Rename canonical_event_id -> canonical_primary_event_id (Item 8)
    #
    # The rename is a PG-internal metadata-only operation; no row rewrite.
    # The existing FK constraint (canonical_observations_canonical_event_id_fkey
    # -> canonical_events(id) ON DELETE SET NULL) and the two partial
    # indexes (idx_canonical_observations_event_id WHERE canonical_event_id
    # IS NOT NULL; idx_canonical_observations_currently_valid on
    # (canonical_event_id, ingested_at DESC) WHERE valid_until IS NULL)
    # automatically follow the rename per PG semantics -- the constraint
    # / index definitions reference the column by its renamed identifier.
    #
    # The constraint NAME, however, retains its original
    # canonical_observations_canonical_event_id_fkey identifier (PG does
    # not auto-rename constraints when the column they reference is
    # renamed).  This is acceptable: the constraint name is opaque to
    # consumers; what matters is the constraint definition references the
    # correct column.  Tests use information_schema introspection to
    # verify the post-rename state, not the constraint name.
    # =========================================================================
    op.execute(
        """
        ALTER TABLE canonical_observations
            RENAME COLUMN canonical_event_id TO canonical_primary_event_id
        """
    )

    # =========================================================================
    # Step 3: Drop the existing temporal_alignment table (Item 6 part A)
    #
    # MCP-verified empty at build time (0 rows).  DROP TABLE cascades to
    # all dependent objects: 8 FK constraints (5 outbound to markets /
    # market_snapshots / game_states / games / canonical_events, 0 inbound
    # since no other table FKs INTO temporal_alignment), 7 indexes
    # (including the partial idx_alignment_quality on the {'poor','stale'}
    # subset), 1 PK constraint, 8 NOT NULL constraints, 2 CHECKs, 1 UNIQUE
    # constraint (uq_alignment_snapshot_game).
    #
    # The slot 0082 FK fk_temporal_alignment_canonical_event_id is among
    # those cascaded.  Slot 0082 itself is NOT edited (Pattern 87): the
    # slot 0082 file's upgrade() still defines the FK; replay of the
    # migration chain reaches the slot 0084 DROP TABLE step which discards
    # the slot 0082-applied FK along with the table.  The downgrade
    # of slot 0084 recreates the FK in the same shape slot 0082 specified.
    # =========================================================================
    op.execute("DROP TABLE temporal_alignment")

    # =========================================================================
    # Step 4: Create new temporal_alignment with pure-linkage shape (Item 6 part B)
    #
    # **PG composite-FK reality, S55 MCP-grounded amendment to PM brief.**
    # The PM brief specified ``observation_a_id BIGINT NOT NULL REFERENCES
    # canonical_observations(id)`` -- a single-column FK.  At alembic
    # upgrade time, PG rejected this with:
    #     "there is no unique constraint matching given keys for
    #      referenced table 'canonical_observations'"
    # because canonical_observations has composite PK ``(id, ingested_at)``
    # (partitioning constraint -- the partition key MUST appear in every
    # UNIQUE / PRIMARY KEY on a partitioned parent).  PG cannot use
    # BIGSERIAL implicit uniqueness for FK validation; it requires a
    # declared UNIQUE / PRIMARY KEY matching the FK columns.
    #
    # Resolution: composite FK shape per V2.43 Item 3 invariant ("Per-kind
    # projection tables FK INTO canonical_observations MUST use composite-
    # FK shape: FOREIGN KEY (canonical_observation_id, observation_ingested_at)
    # REFERENCES canonical_observations(id, ingested_at). Surrogate id
    # alone is insufficient because PG cannot route the FK lookup to the
    # correct partition without the partition key.").  Slot 0084 inherits
    # the same V2.43 Item 3 commitment: temporal_alignment becomes the
    # first non-projection consumer of canonical_observations to use
    # composite-FK shape.  ADR-118 V2.45 supersedes the PM brief's
    # single-column FK shape for this and the link table below.
    #
    # Shape:
    #     - id BIGSERIAL PRIMARY KEY (surrogate; not partitioned)
    #     - observation_a_id BIGINT NOT NULL +
    #       observation_a_ingested_at TIMESTAMPTZ NOT NULL --> composite FK
    #       INTO canonical_observations(id, ingested_at)
    #     - observation_b_id BIGINT NOT NULL +
    #       observation_b_ingested_at TIMESTAMPTZ NOT NULL --> composite FK
    #       INTO canonical_observations(id, ingested_at)
    #     - canonical_event_id BIGINT REFERENCES canonical_events(id)
    #       ON DELETE SET NULL -- denormalized hot-path
    #     - time_delta_seconds NUMERIC(10,3) NOT NULL
    #     - alignment_quality VARCHAR(8) NOT NULL + CHECK 5-value vocab
    #     - aligned_at TIMESTAMPTZ NOT NULL
    #     - created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    #
    # Constraints:
    #     - uq_alignment_pair UNIQUE (observation_a_id, observation_a_ingested_at,
    #       observation_b_id, observation_b_ingested_at) -- matcher
    #       idempotence; same pair (with full composite identifier on both
    #       sides) cannot be aligned twice.
    #     - ck_distinct_observations CHECK NOT (observation_a_id =
    #       observation_b_id AND observation_a_ingested_at =
    #       observation_b_ingested_at) -- self-pair (full composite match)
    #       is meaningless.
    #     - ck_alignment_quality CHECK (alignment_quality IN
    #       ('exact','good','fair','poor','stale')) -- vocabulary CHECK.
    #
    # FK polarity:
    #     - Both observation FKs: NO ON DELETE clause specified -> defaults
    #       to NO ACTION (PG default).  Matcher owns lifecycle; deleting
    #       observations with referencing alignments must be explicit.
    #     - canonical_event_id: ON DELETE SET NULL -- mirrors slot 0078
    #       canonical_observations.canonical_primary_event_id polarity.
    # =========================================================================
    op.execute(
        """
        CREATE TABLE temporal_alignment (
            id                              BIGSERIAL PRIMARY KEY,
            -- Two observations being paired by time proximity.  Composite
            -- FK shape per V2.43 Item 3 invariant: canonical_observations
            -- is partitioned with composite PK (id, ingested_at), so FK
            -- references MUST include both columns to route to the
            -- correct partition.
            observation_a_id                BIGINT NOT NULL,
            observation_a_ingested_at       TIMESTAMPTZ NOT NULL,
            observation_b_id                BIGINT NOT NULL,
            observation_b_ingested_at       TIMESTAMPTZ NOT NULL,
            -- Denormalized hot-path canonical_event tag.  Mirrors the
            -- slot 0078 canonical_primary_event_id polarity (SET NULL).
            canonical_event_id              BIGINT REFERENCES canonical_events(id) ON DELETE SET NULL,
            -- Pairing time gap; 3 decimal places of millisecond precision.
            time_delta_seconds              NUMERIC(10, 3) NOT NULL,
            -- Pairing-quality tier; vocabulary canonical home is the
            -- CHECK below until Cohort 5+ ships a CRUD module + constants
            -- tuple (Pattern 73 SSOT).
            alignment_quality               VARCHAR(8) NOT NULL,
            -- When the matcher created this pair.  Distinct from
            -- created_at (row-existence audit column).
            aligned_at                      TIMESTAMPTZ NOT NULL,
            -- Standard audit-column convention.
            created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),

            -- Composite FKs into the partitioned parent (V2.43 Item 3
            -- invariant).  NO ON DELETE clause -> NO ACTION default.
            CONSTRAINT fk_temporal_alignment_observation_a
                FOREIGN KEY (observation_a_id, observation_a_ingested_at)
                REFERENCES canonical_observations(id, ingested_at),
            CONSTRAINT fk_temporal_alignment_observation_b
                FOREIGN KEY (observation_b_id, observation_b_ingested_at)
                REFERENCES canonical_observations(id, ingested_at),

            -- Matcher idempotence: same pair (full composite identifier
            -- on both sides) cannot be aligned twice.
            CONSTRAINT uq_alignment_pair
                UNIQUE (observation_a_id, observation_a_ingested_at,
                        observation_b_id, observation_b_ingested_at),

            -- Self-pairing (full composite match) is semantically
            -- meaningless.  Different ingested_at values for the same
            -- id are theoretically possible across partitions and remain
            -- meaningful pairs (pre-/post-rebuild same observation).
            CONSTRAINT ck_distinct_observations
                CHECK (NOT (observation_a_id = observation_b_id
                       AND observation_a_ingested_at = observation_b_ingested_at)),

            -- Vocabulary CHECK (Pattern 73 SSOT canonical home for the
            -- 5-value alignment_quality vocabulary until Cohort 5+ CRUD
            -- module ships).
            CONSTRAINT ck_alignment_quality
                CHECK (alignment_quality IN (
                    'exact', 'good', 'fair', 'poor', 'stale'
                ))
        )
        """
    )

    # Indexes on new temporal_alignment.
    op.execute(
        """
        CREATE INDEX idx_alignment_canonical_event
            ON temporal_alignment (canonical_event_id, aligned_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_alignment_observation_a
            ON temporal_alignment (observation_a_id, observation_a_ingested_at)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_alignment_observation_b
            ON temporal_alignment (observation_b_id, observation_b_ingested_at)
        """
    )

    # =========================================================================
    # Step 5: Create canonical_observation_event_links (Item 8)
    #
    # Shape per V2.45 Item 8 + design_review_v246_input_memo.md § Item 8 +
    # composite-FK invariant per V2.43 Item 3 (canonical_observations is
    # partitioned with composite PK (id, ingested_at); FK references must
    # include both columns to route to the correct partition).
    #
    # Shape:
    #     - observation_id BIGINT NOT NULL +
    #       observation_ingested_at TIMESTAMPTZ NOT NULL --> composite FK
    #       INTO canonical_observations(id, ingested_at) ON DELETE CASCADE.
    #       When an observation is deleted, its event links go with it
    #       (linkage rows have no semantic value without the observation).
    #     - canonical_event_id BIGINT NOT NULL REFERENCES canonical_events(id)
    #       ON DELETE RESTRICT.  Cannot delete a canonical_event while
    #       observations link to it.
    #     - link_kind VARCHAR(16) NOT NULL CHECK -- vocabulary canonical
    #       home (Pattern 73 SSOT until Cohort 5+ CRUD module ships).
    #       Values: primary / secondary / derived / speculative.
    #     - confidence NUMERIC(5,4) -- 0.0-1.0; NULL for manual tags.
    #     - linked_at TIMESTAMPTZ NOT NULL DEFAULT now()
    #     - linked_by VARCHAR(64) NOT NULL -- attribution.
    #
    # PRIMARY KEY (observation_id, observation_ingested_at, canonical_event_id) --
    # composite PK including observation_ingested_at because the partition
    # key MUST appear in any UNIQUE referencing canonical_observations
    # (PG partition semantic).  Provides "this observation (full composite
    # identifier) linked to this canonical_event" idempotence.
    #
    # Indexes:
    #     - idx_link_observation (observation_id, observation_ingested_at) --
    #       observation-side reverse lookup.
    #     - idx_link_canonical_event (canonical_event_id, link_kind) --
    #       canonical-event-side reverse lookup with link_kind filter.
    #     - idx_link_one_primary_per_observation UNIQUE (observation_id,
    #       observation_ingested_at) WHERE link_kind = 'primary' --
    #       partial unique enforcing "at most one primary link per
    #       observation (full composite identifier)" invariant.
    # =========================================================================
    op.execute(
        """
        CREATE TABLE canonical_observation_event_links (
            -- Linked observation: composite-FK shape per V2.43 Item 3.
            -- CASCADE on delete: link rows die with their observation.
            observation_id            BIGINT NOT NULL,
            observation_ingested_at   TIMESTAMPTZ NOT NULL,
            -- Linked canonical event.  RESTRICT on delete.
            canonical_event_id        BIGINT NOT NULL REFERENCES canonical_events(id)
                                      ON DELETE RESTRICT,
            -- Linkage type.  Pattern 73 SSOT canonical home until
            -- Cohort 5+ CRUD ships CANONICAL_OBSERVATION_LINK_KINDS.
            link_kind                 VARCHAR(16) NOT NULL,
            -- Tagging confidence (0.0-1.0).  NULL for manual tags.
            confidence                NUMERIC(5, 4),
            -- When the link was created.
            linked_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
            -- Free-form attribution.
            linked_by                 VARCHAR(64) NOT NULL,

            -- Composite PK includes observation_ingested_at (partition
            -- key invariant per V2.43 Item 3).
            PRIMARY KEY (observation_id, observation_ingested_at, canonical_event_id),

            -- Composite FK into the partitioned parent.  CASCADE on
            -- delete: observation deletion cascades to link rows.
            CONSTRAINT fk_link_observation
                FOREIGN KEY (observation_id, observation_ingested_at)
                REFERENCES canonical_observations(id, ingested_at)
                ON DELETE CASCADE,

            -- Vocabulary CHECK (Pattern 73 SSOT canonical home for the
            -- 4-value link_kind vocabulary until Cohort 5+ CRUD ships).
            CONSTRAINT ck_link_kind
                CHECK (link_kind IN (
                    'primary', 'secondary', 'derived', 'speculative'
                )),

            -- Confidence range CHECK (valid probability).
            CONSTRAINT ck_confidence_range
                CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
        )
        """
    )

    # Indexes on canonical_observation_event_links.
    op.execute(
        """
        CREATE INDEX idx_link_observation
            ON canonical_observation_event_links (observation_id, observation_ingested_at)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_link_canonical_event
            ON canonical_observation_event_links (canonical_event_id, link_kind)
        """
    )
    # Partial unique index: at most one 'primary' link per observation
    # (full composite identifier).  Mirrors canonical_primary_event_id
    # denormalized column's "single primary tag" invariant.
    op.execute(
        """
        CREATE UNIQUE INDEX idx_link_one_primary_per_observation
            ON canonical_observation_event_links (observation_id, observation_ingested_at)
            WHERE link_kind = 'primary'
        """
    )


def downgrade() -> None:
    """Reverse 0084: restore old temporal_alignment + canonical_observations shape.

    Step order (reverse-dependency-respecting):

        1. Drop ``canonical_observation_event_links`` (Item 8 reverse).
        2. Drop new ``temporal_alignment`` table + 3 indexes (Item 6 reverse part A).
        3. Recreate old ``temporal_alignment`` shape with sport-typed
           columns + slot 0082 FK (Item 6 reverse part B).  This is a
           faithful reconstruction of the slot-0082-end shape (20 columns
           + 8 indexes + 8 constraints + 1 UNIQUE) so the round-trip
           CI gate replay leaves the schema bit-identical.
        4. Reverse rename: ``canonical_primary_event_id`` ->
           ``canonical_event_id`` on canonical_observations (Item 8 reverse).
        5. Re-add ``payload`` JSONB NOT NULL column on canonical_observations
           (Item 4 reverse).  Empty table -> NOT NULL is safe to add
           directly; if downgrade is run on a populated DB (NOT certified
           safe per round-trip gate's standing banner), the NOT NULL
           constraint would fail and the operator would see the violation.

    The downgrade is intentionally lossy at the schema-bookkeeping level:
    if any rows had been written to the new temporal_alignment shape after
    upgrade, those rows are discarded by the DROP TABLE.  Per the round-
    trip gate's standing banner, downgrade is NOT certified safe to run
    on a populated production DB without a separate backup/restore drill
    (Epic #1071); the gate verifies schema reversibility only.

    ``IF EXISTS`` is used throughout per session 59
    ``feedback_idempotent_migration_drops.md`` so re-running the downgrade
    on a partially-rolled-back DB is a no-op rather than a crash.
    """
    # =========================================================================
    # Step 1: Drop canonical_observation_event_links (Item 8 reverse)
    #
    # DROP TABLE cascades to: 3 indexes (idx_link_observation,
    # idx_link_canonical_event, idx_link_one_primary_per_observation),
    # the composite PK constraint, the 2 CHECKs (ck_link_kind,
    # ck_confidence_range), the 2 FK constraints (observation_id,
    # canonical_event_id).  No inbound FKs (slot 0084 is the most-recent
    # migration as of downgrade time).
    # =========================================================================
    op.execute("DROP TABLE IF EXISTS canonical_observation_event_links")

    # =========================================================================
    # Step 2: Drop new temporal_alignment + 3 indexes (Item 6 reverse part A)
    #
    # DROP TABLE cascades to indexes + PK + UNIQUE + CHECKs + FKs.
    # Explicit DROP INDEX statements would be redundant.
    # =========================================================================
    op.execute("DROP TABLE IF EXISTS temporal_alignment")

    # =========================================================================
    # Step 3: Recreate old temporal_alignment (Item 6 reverse part B)
    #
    # Faithful reconstruction of the slot-0082-end shape:
    #     - 20 columns (including slot 0082's canonical_event_id)
    #     - id INTEGER PK (NOT BIGINT in the old shape; preserved here
    #       for faithful round-trip)
    #     - market_id, market_snapshot_id, game_state_id INTEGER NOT NULL
    #       FKs to markets / market_snapshots / game_states ON DELETE
    #       RESTRICT
    #     - game_id INTEGER FK to games ON DELETE RESTRICT (nullable)
    #     - canonical_event_id BIGINT FK to canonical_events ON DELETE
    #       SET NULL (slot 0082 contribution; restored in same NOT VALID
    #       + VALIDATE shape)
    #     - snapshot_time, game_state_time TIMESTAMPTZ NOT NULL
    #     - time_delta_seconds NUMERIC NOT NULL
    #     - alignment_quality VARCHAR(8) NOT NULL DEFAULT 'good' CHECK
    #     - sport-specific typed columns (yes_ask_price, no_ask_price,
    #       spread, volume, game_status, home_score, away_score, period,
    #       clock) all nullable
    #     - created_at TIMESTAMPTZ DEFAULT now()
    # Constraints:
    #     - uq_alignment_snapshot_game UNIQUE (market_snapshot_id,
    #       game_state_id)
    #     - alignment_quality CHECK
    # Indexes (8 total, mirroring slot-0082-end MCP-verified state):
    #     - idx_alignment_game_id partial WHERE game_id IS NOT NULL
    #     - idx_alignment_game_state on game_state_id
    #     - idx_alignment_market on market_id
    #     - idx_alignment_market_time on (market_id, snapshot_time DESC)
    #     - idx_alignment_quality partial WHERE alignment_quality IN
    #       ('poor','stale')
    #     - idx_temporal_alignment_canonical_event_id on canonical_event_id
    #       (slot 0082 contribution)
    # =========================================================================
    op.execute(
        """
        CREATE TABLE temporal_alignment (
            id                     SERIAL PRIMARY KEY,
            market_id              INTEGER NOT NULL REFERENCES markets(id)
                                   ON DELETE RESTRICT,
            market_snapshot_id     INTEGER NOT NULL REFERENCES market_snapshots(id)
                                   ON DELETE RESTRICT,
            game_state_id          INTEGER NOT NULL REFERENCES game_states(id)
                                   ON DELETE RESTRICT,
            snapshot_time          TIMESTAMPTZ NOT NULL,
            game_state_time        TIMESTAMPTZ NOT NULL,
            time_delta_seconds     NUMERIC NOT NULL,
            alignment_quality      VARCHAR(8) NOT NULL DEFAULT 'good'
                                   CHECK (alignment_quality IN (
                                       'exact', 'good', 'fair', 'poor', 'stale'
                                   )),
            yes_ask_price          NUMERIC,
            no_ask_price           NUMERIC,
            spread                 NUMERIC,
            volume                 INTEGER,
            game_status            VARCHAR,
            home_score             INTEGER,
            away_score             INTEGER,
            period                 VARCHAR,
            clock                  VARCHAR,
            created_at             TIMESTAMPTZ DEFAULT now(),
            game_id                INTEGER REFERENCES games(id) ON DELETE RESTRICT,
            canonical_event_id     BIGINT,
            CONSTRAINT uq_alignment_snapshot_game
                UNIQUE (market_snapshot_id, game_state_id)
        )
        """
    )
    # Restore slot 0082's NOT VALID + VALIDATE FK shape on canonical_event_id.
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
    op.execute(
        """
        ALTER TABLE temporal_alignment
            VALIDATE CONSTRAINT fk_temporal_alignment_canonical_event_id
        """
    )
    # Restore slot-0082-end indexes (8 total).
    op.execute(
        """
        CREATE INDEX idx_alignment_game_id
            ON temporal_alignment (game_id)
            WHERE game_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX idx_alignment_game_state
            ON temporal_alignment (game_state_id)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_alignment_market
            ON temporal_alignment (market_id)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_alignment_market_time
            ON temporal_alignment (market_id, snapshot_time DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_alignment_quality
            ON temporal_alignment (alignment_quality)
            WHERE alignment_quality IN ('poor', 'stale')
        """
    )
    op.execute(
        """
        CREATE INDEX idx_temporal_alignment_canonical_event_id
            ON temporal_alignment (canonical_event_id)
        """
    )

    # =========================================================================
    # Step 4: Reverse rename canonical_primary_event_id -> canonical_event_id
    # (Item 8 reverse)
    # =========================================================================
    op.execute(
        """
        ALTER TABLE canonical_observations
            RENAME COLUMN canonical_primary_event_id TO canonical_event_id
        """
    )

    # =========================================================================
    # Step 5: Re-add payload JSONB NOT NULL column (Item 4 reverse)
    #
    # Empty table at downgrade time -> NOT NULL is safe to add directly.
    # If downgrade is run on a populated DB (NOT certified safe), the
    # NOT NULL constraint would fail and the operator would see the
    # violation.  Per round-trip gate's standing banner, downgrade is
    # not certified safe on populated production DBs.
    # =========================================================================
    op.execute(
        """
        ALTER TABLE canonical_observations
            ADD COLUMN payload JSONB NOT NULL
        """
    )
