"""Cohort 4 first slot — ``canonical_observations`` partitioned parent table.

Lands the **partitioned parent observation table** for the canonical-tier
ingest pipeline.  Every cross-domain observation (game state, weather,
poll, econ print, news event, market snapshot — full kind set per
``OBSERVATION_KIND_VALUES``) writes one row here through the restricted
CRUD function ``crud_canonical_observations.append_observation_row()``.
Per-kind projection tables (``weather_observations``, ``poll_releases``,
etc.) materialize in Cohort 9+; Cohort 4 only exercises the ``game_state``
kind.

Per session 85 4-agent design council (Galadriel + Holden + Miles + Uhura
paired-cluster, CLEAR-WITH-NOTES) + session 86 user adjudication of 5
council items + ADR-118 V2.43 amendment (Cohort 4 scope lock + cohort
numbering canonicalization + Phase B.5 #4 split) + session 86 PM-composed
build spec at ``memory/build_spec_0078_pm_memo.md`` (S82 INHERITED — no
material drift vs council scope).

Slot 0078 ships:
    - ONE partitioned parent table (``canonical_observations``) with
      composite PK ``(id, ingested_at)``, RANGE-partitioned on
      ``ingested_at`` monthly (PARTITION_STRATEGY_VALUES =
      ``'range_monthly_ingested_at'``).
    - FOUR pre-created monthly partitions (2026-05/06/07/08) covering
      the session 86-90 soak window.
    - FIVE indexes (Holden + Miles convergent set; partial WHERE
      predicates for cross-domain efficiency).
    - ONE composite UNIQUE on ``(source_id, payload_hash, ingested_at)``
      for restart idempotence (composite-FK-on-partition-PK invariant
      per V2.43 Item 3 — ``ingested_at`` MUST appear in every UNIQUE on a
      partitioned parent).
    - THREE CHECK constraints: ``observation_kind`` 6-value vocab,
      clock-skew guard (``source_published_at <= ingested_at + interval
      '5 minutes'``), bitemporal validity well-formedness.
    - ONE BEFORE UPDATE trigger ``trg_canonical_observations_updated_at``
      using slot 0076's generic ``set_updated_at()`` function (Pattern 73
      SSOT — one chokepoint for canonical-tier ``updated_at`` maintenance).

What slot 0078 deliberately does NOT include (scope fence):

    * No per-kind projection tables (``weather_observations``,
      ``poll_releases``, ``econ_prints``, ``news_events``,
      ``market_snapshots_canonical``) — Cohort 9+ per Master Requirements
      + Option D weather deferral.
    * No ``canonical_event_phase_log`` — slot 0079 (cheap close-out).
    * No ``games.canonical_event_id`` / ``game_states.canonical_event_id``
      nullable FKs — slot 0080-combined territory.
    * No ``temporal_alignment.canonical_event_id`` FK — slot 0082.
    * No ``v_temporal_alignment`` rewire — slot 0083.
    * No ``canonical_reconciliation_results`` typed-result table —
      Cohort 5+ per V2.43 Item 4.
    * No reconciler manual-CLI — Cohort 4 separate slot/PR after writer
      soak (V2.43 micro-delta MD1).
    * No append-only enforcement trigger — application discipline only
      (mirrors slot 0073 precedent; trigger queued for post-soak slot
      after baseline ingest-rate measurements).
    * No backfill of historical observations — current-only
      ``row_current_ind=true`` ingestion for Cohort 4 (council convergence).

Pattern 73 SSOT — three new vocabulary tuples in
``src/precog/database/constants.py``:

    ``OBSERVATION_KIND_VALUES``       — 6-value DDL-CHECK-backed vocab
                                        (game_state, weather, poll, econ,
                                        news, market_snapshot).  Mirrors
                                        the inline CHECK on
                                        ``canonical_observations.observation_kind``.
    ``PARTITION_STRATEGY_VALUES``     — documentation-only tuple
                                        (``range_monthly_ingested_at``).
                                        No DDL CHECK; PG partitioning
                                        encodes the strategy in the
                                        ``PARTITION BY`` clause itself.
    ``RECONCILIATION_OUTCOME_VALUES`` — 6-value vocab for the future
                                        Cohort 5+ reconciler.  Defined
                                        here so the reconciler inherits
                                        a stable vocabulary at landing.

The ``crud_canonical_observations`` module imports
``OBSERVATION_KIND_VALUES`` in real-guard ``ValueError``-raising
validation (the slot-0073-strengthened convention; NOT side-effect-only
``# noqa: F401`` import).

Pattern 81 carve-out: ``observation_kind`` is intentionally NOT a lookup
table.  The kind set is closed (every value binds to per-kind projection
code in later cohorts per Pattern 81 § "When NOT to Apply"); adding a new
kind requires a code deploy regardless of where the vocabulary lives.
Same carve-out shape as ``LINK_STATE_VALUES`` / ``ACTION_VALUES`` /
``REVIEW_STATE_VALUES`` / ``POLARITY_VALUES``.

Pattern 84 (NOT VALID + VALIDATE for CHECK on populated tables) — N/A:

    Fresh empty parent table; ``canonical_observations`` does not exist
    before this migration.  No seed paths; the first row is written by
    Cohort 5+ writer code at runtime via
    ``append_observation_row()``.  Per Pattern 84 § "When NOT to Apply"
    both criteria met (zero rows in dev/staging/prod at migration time;
    no expected rows by production deploy time — feature flag
    ``features.canonical_observations_writer.enabled`` defaults to
    ``false`` until session 87 soak window).

Pattern 87 (Append-only migrations) — REAFFIRMED CLEAN:

    Slot 0078 is a NEW migration file; Pattern 87 fires when editing
    PREVIOUSLY-MERGED migrations.  This PR makes ZERO edits to migrations
    0001-0077.  The constants.py extension + schedulers/service_supervisor.py
    edit + new CRUD module + new operator runbook + new tests are all
    application code or documentation, all editable freely.

Composite UNIQUE invariant + ``ingested_at`` requirement (V2.43 Item 3):

    ``UNIQUE (source_id, payload_hash, ingested_at)`` — the partition
    column ``ingested_at`` MUST appear in every UNIQUE constraint on a
    partitioned parent table per PG partitioning semantics.  Omitting
    ``ingested_at`` here would surface as
    ``insufficient columns in UNIQUE constraint definition`` at
    migration apply time.

    The dedup contract is **(source_id, payload_hash) within a single
    partition window** — a payload that lands in May 2026 and the same
    payload re-landing in June 2026 are NOT considered duplicates by
    this UNIQUE.  This is intentional: a re-published source observation
    crossing a partition boundary is a legitimately fresh ingest event
    (the source likely re-emitted with updated metadata or after a
    correction), not a duplicate.  Cross-partition dedup, if needed, is
    a future-cohort surface (Cohort 5+ reconciler can detect the same
    payload_hash across partition windows via cross-partition SELECT).

Composite PK + composite-FK invariant (V2.43 Item 3):

    ``PRIMARY KEY (id, ingested_at)`` — composite PK because PG requires
    the partition key to be part of every UNIQUE / PRIMARY KEY constraint
    on a partitioned parent.  Per-kind projection tables (Cohort 9+) FK
    INTO ``canonical_observations`` MUST use composite-FK shape:
    ``FOREIGN KEY (canonical_observation_id, observation_ingested_at)
    REFERENCES canonical_observations(id, ingested_at)``.  Surrogate
    ``id`` alone is insufficient (PG cannot route the FK lookup to the
    correct partition without the partition key).  Forward-pointer for
    Cohort 9+ projection authors so they don't reinvent the FK shape.

Five-timestamp ML causal-correctness commitment (Holden D2 PM call):

    Slot 0078 commits to FIVE timestamp columns rather than the 3-column
    minimum Miles's operational frame proposed.  Each carries distinct
    semantics; conflating any two would silently corrupt point-in-time
    replay queries:

        ``event_occurred_at``    NULL OK.  Real-world event timestamp
                                 (e.g., when the play happened on the
                                 field).  NULL for observations with no
                                 clear event time (econ prints aggregate
                                 over a window; news events are
                                 publication-time-only).
        ``source_published_at``  NOT NULL.  When the source emitted the
                                 observation (e.g., ESPN's payload publish
                                 time).  Reconciler queries use this as
                                 the "what did the source claim, when did
                                 they claim it" anchor.
        ``ingested_at``          NOT NULL.  When we received the
                                 observation.  Partition key.  Drives
                                 monthly partition routing.
        ``valid_at``             NOT NULL.  Bitemporal "valid from".
                                 Enables point-in-time replay queries:
                                 "what did the system know about this
                                 event AS OF time T?"
        ``valid_until``          NULL OK.  Bitemporal "valid until".
                                 NULL = currently-valid (open-ended
                                 interval).  Mirrors the SCD-2 shape from
                                 ``market_snapshots`` / ``game_states``.

    Causal-correctness query template (Cohort 5+ ML feature pipelines):

        SELECT * FROM canonical_observations
        WHERE valid_at <= $as_of
          AND (valid_until IS NULL OR valid_until > $as_of)
          AND ingested_at <= $as_of   -- causal-correctness: only
                                       -- observations available at $as_of
        ORDER BY ingested_at DESC;

    The ``ingested_at <= $as_of`` clause is the causal-correctness
    discipline: a feature pipeline replaying decisions at time T MUST
    only see observations the system actually had ingested by T.

Clock-skew CHECK rationale (Miles operational-feasibility frame):

    ``CHECK (source_published_at <= ingested_at + interval '5 minutes')``
    — guards against two failure modes:

        1. Source-side clock drift exceeding 5 minutes ahead of our
           clock (the source claims to have published the data 10 minutes
           in our future).  CHECK fires; CRUD layer surfaces a
           ``CheckViolation`` to the writer; writer logs + skips +
           emits a clock-skew metric.  Downstream alert surfaces the
           anomaly rather than admitting potentially-corrupt data.
        2. Test-fixture clock-skew bugs (a fixture sets
           ``source_published_at`` to an arbitrary far-future timestamp).
           CHECK catches the bug at fixture-creation time rather than
           letting the bug propagate into reconciler code.

    5-minute tolerance is intentionally generous: typical source clock
    drift is sub-second, but network jitter + retry latency can push
    apparent drift to ~30 seconds during peak load.  5 minutes
    accommodates the 99th percentile of observed network latency
    without admitting genuine clock-corruption events.

Bitemporal validity CHECK rationale:

    ``CHECK (valid_until IS NULL OR valid_until >= valid_at)`` — guards
    against bitemporal interval well-formedness violations.  A row with
    ``valid_until < valid_at`` is semantically meaningless ("valid from
    later to earlier" is not a valid interval); the CHECK surfaces the
    bug at write time rather than letting it propagate into replay
    queries.

BEFORE UPDATE trigger (slot 0076 generic ``set_updated_at()`` reuse):

    ``CREATE TRIGGER trg_canonical_observations_updated_at BEFORE UPDATE
    ON canonical_observations FOR EACH ROW EXECUTE FUNCTION
    set_updated_at()``.  Naming convention follows slot 0076's
    canonical-tier retrofit precedent (``trg_<table>_updated_at``).

    The trigger is installed on the PARENT table; PG propagates trigger
    semantics to every partition automatically (BEFORE UPDATE on
    ``canonical_observations_2026_05`` invokes the parent trigger).  No
    per-partition trigger DDL is required.

    ``updated_at`` column is NULLABLE (per V2.42 sub-amendment A
    convention — nullable updated_at REQUIRES the BEFORE UPDATE trigger
    to maintain freshness; the trigger is the contract that says "any
    DB-side UPDATE bumps updated_at, including FK-NULL cascades from
    ``canonical_events`` deletes").

FK polarity rationale (V2.43 Item 2 + slot 0077 silent-fail/loud-fail
asymmetry):

    ``source_id BIGINT NOT NULL REFERENCES observation_source(id) ON
    DELETE RESTRICT`` — the source registry is authoritative; deleting
    a source row while observations reference it is a bug, not a
    legitimate operation.  RESTRICT surfaces it loud.

    ``canonical_event_id BIGINT REFERENCES canonical_events(id) ON
    DELETE SET NULL`` — mirrors V2.42 sub-amendment B + V2.43 Item 2
    canonical-tier polarity.  SET NULL preserves the observation row
    while NULLing the link; the canonical_event row deletion is the
    upstream operator action, observation history outlives.  Cross-
    domain observations (weather, econ, news in future cohorts) are
    not always tied to a canonical_event, so the column is NULLABLE
    from creation.

Five-index strategy rationale (Holden + Miles convergent set):

    1. ``idx_canonical_observations_event_id`` (partial WHERE
       ``canonical_event_id IS NOT NULL``) — the partial form keeps the
       index small because cross-domain observations (Cohorts 6-9) will
       have NULL ``canonical_event_id`` for the majority of rows.
    2. ``idx_canonical_observations_kind_ingested`` ((``observation_kind``,
       ``ingested_at`` DESC)) — common query: "latest game_state
       observations" / "latest weather observations".
    3. ``idx_canonical_observations_source_published``
       ((``source_id``, ``source_published_at`` DESC)) — common query:
       "what did source X publish since timestamp Y" (poller heartbeat
       checks).
    4. ``idx_canonical_observations_event_occurred``
       (``event_occurred_at`` DESC, partial WHERE
       ``event_occurred_at IS NOT NULL``) — ML causal-correctness
       queries by event time.
    5. ``idx_canonical_observations_currently_valid``
       ((``canonical_event_id``, ``ingested_at`` DESC), partial WHERE
       ``valid_until IS NULL``) — SCD-2-style "currently-valid" view
       (mirrors ``row_current_ind=TRUE`` pattern from existing tables).

    Per PG partitioning: indexes on the partitioned parent are NOT
    automatically materialized as full partition-spanning indexes;
    instead each partition gets its own index instance with the same
    name pattern.  PG12+ supports the parent-level CREATE INDEX
    syntax which transparently materializes per-partition indexes —
    the migration uses parent-level CREATE INDEX for clarity.

Round-trip discipline (PR #1081 round-trip CI gate):

    PR #1081 ships the round-trip CI gate as Epic #1071's first slot
    (merged session 80).  Slot 0078's ``downgrade()`` is a pure inverse
    of ``upgrade()``: every CREATE has a matching ``DROP IF EXISTS`` in
    downgrade.  Drop order respects object dependencies (trigger →
    indexes → partitions → parent table).  The round-trip gate auto-
    discovers slot 0078 on push and runs ``downgrade -> upgrade head``
    against it; no Builder action needed beyond clean upgrade/downgrade
    pairing.

Builder-question resolutions (build spec § 11):

    1. ``payload_hash`` derivation: SHA-256 of canonicalized JSON
       (``json.dumps(payload, sort_keys=True, separators=(',', ':'))``).
       BYTEA column type allows future algorithm swap (SHA-3) without
       DDL break.  Cohort 1 ``canonical_markets.natural_key_hash``
       deferral precedent mirrored.
    2. Partition naming: ``canonical_observations_YYYY_MM`` per spec;
       no project-wide divergence found in the codebase.
    3. Trigger naming: ``trg_canonical_observations_updated_at``
       follows slot 0076's established ``trg_<table>_updated_at``
       convention (verified against
       ``0076_set_updated_at_generic.py``).
    4. Operator runbook home: ``docs/operations/`` does NOT exist
       pre-slot-0078; created per Uhura S82 recommendation.
    5. Feature-flag location: ``features.<flag_name>`` matches the
       existing pattern in ``src/precog/config/system.yaml`` (other
       feature flags include ``features.websockets``,
       ``features.live_trading``).  Slot 0078 adds
       ``features.canonical_observations_writer.enabled`` (nested
       per-feature subkey for forward-extensibility — future Cohort 5+
       reconciler config will use
       ``features.canonical_observations_writer.reconcile_interval``
       etc. without further schema churn).

Revision ID: 0078
Revises: 0077
Create Date: 2026-05-01

Issue: Epic #972 (Canonical Layer Foundation — Phase B.5)
ADR: ADR-118 V2.43 Cohort 4 (canonical_observations partitioned parent
    + composite PK + composite-FK invariant + 5-timestamp DDL +
    OBSERVATION_KIND_VALUES + RECONCILIATION_OUTCOME_VALUES)
Build spec: ``memory/build_spec_0078_pm_memo.md``
S82: ``memory/s82_slot_0078_inherited_memo.md`` (CLEAR-TO-DISPATCH —
    inherited from session 85 4-agent council; no material drift)
Council: session 85 4-agent paired-cluster (Galadriel + Holden + Miles +
    Uhura) at ``memory/design_review_cohort4_synthesis.md``
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0078"
down_revision: str = "0077"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Pre-created partition specs.  Pattern 73 SSOT canonical home for the slot
# 0078 partition set — the same 4 partitions are referenced by the integration
# test (``test_migration_0078_canonical_observations.py``) and the operator
# runbook (``docs/operations/canonical_observations_runbook.md``).  Adding
# the next monthly partition is the operator runbook procedure (~7 days
# before the latest partition expires); Builder MUST NOT extend this list
# in slot 0078 itself — partition addition is operational, not migration-
# scope.
_INITIAL_PARTITIONS: tuple[tuple[str, str, str], ...] = (
    # (partition_table_name, lower_bound_inclusive, upper_bound_exclusive)
    ("canonical_observations_2026_05", "2026-05-01", "2026-06-01"),
    ("canonical_observations_2026_06", "2026-06-01", "2026-07-01"),
    ("canonical_observations_2026_07", "2026-07-01", "2026-08-01"),
    ("canonical_observations_2026_08", "2026-08-01", "2026-09-01"),
)
"""Monthly partitions pre-created by slot 0078 covering session 86-90 soak.

Operators add the next month's partition ~7 days before the latest in this
set expires (per ``docs/operations/canonical_observations_runbook.md`` §
Partition addition runbook).  This list documents the slot-0078 baseline;
post-slot operations extend coverage forward via ad-hoc CREATE TABLE ...
PARTITION OF statements (idempotent under re-run when wrapped with
``IF NOT EXISTS`` per the runbook template)."""


# Five indexes on the partitioned parent (Holden + Miles convergent set).
# Pattern 73 SSOT canonical home — the integration test asserts the same
# names + same partial-WHERE shapes via parametrize.  Drift here ->
# integration test fires.
_INDEX_DEFINITIONS: tuple[tuple[str, str], ...] = (
    (
        "idx_canonical_observations_event_id",
        "CREATE INDEX idx_canonical_observations_event_id "
        "ON canonical_observations (canonical_event_id) "
        "WHERE canonical_event_id IS NOT NULL",
    ),
    (
        "idx_canonical_observations_kind_ingested",
        "CREATE INDEX idx_canonical_observations_kind_ingested "
        "ON canonical_observations (observation_kind, ingested_at DESC)",
    ),
    (
        "idx_canonical_observations_source_published",
        "CREATE INDEX idx_canonical_observations_source_published "
        "ON canonical_observations (source_id, source_published_at DESC)",
    ),
    (
        "idx_canonical_observations_event_occurred",
        "CREATE INDEX idx_canonical_observations_event_occurred "
        "ON canonical_observations (event_occurred_at DESC) "
        "WHERE event_occurred_at IS NOT NULL",
    ),
    (
        "idx_canonical_observations_currently_valid",
        "CREATE INDEX idx_canonical_observations_currently_valid "
        "ON canonical_observations (canonical_event_id, ingested_at DESC) "
        "WHERE valid_until IS NULL",
    ),
)
"""Five indexes on canonical_observations.  Names + DDL pinned here so the
integration test parametrize shares the canonical home (Pattern 73 SSOT)."""


def upgrade() -> None:
    """Create canonical_observations parent + 4 partitions + 5 indexes + trigger.

    Step order:

        1. ``canonical_observations`` parent table (CREATE TABLE ...
           PARTITION BY RANGE (ingested_at) with all FK clauses + 3
           inline CHECK constraints + 1 dedup UNIQUE + composite PK).
        2. Four monthly partitions (CREATE TABLE ... PARTITION OF ...
           FOR VALUES FROM ... TO ...) covering 2026-05 through 2026-08.
        3. Five indexes (Holden + Miles convergent set; partial WHERE
           predicates per build spec § 2).
        4. BEFORE UPDATE trigger ``trg_canonical_observations_updated_at``
           pointing at slot 0076's generic ``set_updated_at()`` function.
    """
    # =========================================================================
    # canonical_observations parent table
    #
    # Column-level rationale (Builder docstring obligation per build spec § 2):
    #   - id BIGSERIAL: surrogate; part of composite PK (id, ingested_at).
    #     Cannot be standalone PK on a partitioned parent because PG
    #     requires the partition key in every UNIQUE/PK.
    #   - observation_kind VARCHAR(32) NOT NULL CHECK (... 6-value set):
    #     Pattern 73 SSOT pointer — canonical home is constants.py
    #     OBSERVATION_KIND_VALUES; CRUD layer uses it in real-guard
    #     ValueError-raising validation.
    #   - source_id BIGINT NOT NULL REFERENCES observation_source(id) ON
    #     DELETE RESTRICT: source registry is authoritative.
    #   - canonical_event_id BIGINT NULL REFERENCES canonical_events(id)
    #     ON DELETE SET NULL: mirrors V2.42 sub-amendment B canonical-tier
    #     polarity; cross-domain observations not always tied to events.
    #   - payload_hash BYTEA NOT NULL: dedup key; SHA-256 of canonicalized
    #     JSON per CRUD-layer _compute_payload_hash().  BYTEA allows
    #     future algorithm swap without DDL break.
    #   - payload JSONB NOT NULL: free-form payload at decision time;
    #     per-kind projections decode this in Cohort 9+.
    #   - event_occurred_at TIMESTAMPTZ NULL: real-world event time.
    #     NULL allowed because some kinds (econ, news) have no clear
    #     event time.
    #   - source_published_at TIMESTAMPTZ NOT NULL: when the source
    #     emitted the observation.  Drives reconciler queries.
    #   - ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(): when we
    #     received it.  PARTITION KEY.
    #   - valid_at TIMESTAMPTZ NOT NULL DEFAULT now(): bitemporal "valid
    #     from" for replay queries.
    #   - valid_until TIMESTAMPTZ NULL: bitemporal "valid until";
    #     NULL = currently-valid (mirrors row_current_ind=TRUE pattern).
    #   - created_at TIMESTAMPTZ NOT NULL DEFAULT now(): canonical
    #     audit-column convention.
    #   - updated_at TIMESTAMPTZ NULL: nullable per V2.42 sub-amendment A
    #     convention; BEFORE UPDATE trigger maintains freshness.
    #
    # PRIMARY KEY (id, ingested_at): composite (id is sequence-generated;
    # ingested_at is the partition key; PG requires the partition key in
    # the PK).
    #
    # UNIQUE (source_id, payload_hash, ingested_at): dedup; ingested_at is
    # included because PG requires the partition key in every UNIQUE on a
    # partitioned parent.  Dedup contract is "within a single partition
    # window"; cross-partition repeated payloads are treated as fresh
    # ingest events.
    # =========================================================================
    op.execute(
        """
        CREATE TABLE canonical_observations (
            id                    BIGSERIAL,
            -- observation_kind vocabulary canonical home:
            -- src/precog/database/constants.py OBSERVATION_KIND_VALUES.
            -- Adding a value requires lockstep update of both the constant
            -- AND the CHECK constraint below (Pattern 73 SSOT discipline).
            observation_kind      VARCHAR(32)  NOT NULL,
            -- source_id RESTRICT: source registry is authoritative.
            -- Deleting a source row while observations reference it is a
            -- bug, not a legitimate operation.
            source_id             BIGINT       NOT NULL REFERENCES observation_source(id) ON DELETE RESTRICT,
            -- canonical_event_id SET NULL: mirrors V2.42 sub-amendment B.
            -- Observation history outlives the canonical_event.  Nullable
            -- because cross-domain observations (Cohorts 6-9) are not
            -- always tied to a canonical_event.
            canonical_event_id    BIGINT       NULL REFERENCES canonical_events(id) ON DELETE SET NULL,
            -- payload_hash dedup key: SHA-256 of canonicalized JSON
            -- (json.dumps(payload, sort_keys=True, separators=(',', ':'))).
            -- BYTEA allows future algorithm swap (SHA-3) without DDL break.
            payload_hash          BYTEA        NOT NULL,
            -- payload free-form snapshot at decision time; per-kind
            -- projections decode this in Cohort 9+.
            payload               JSONB        NOT NULL,
            -- Five timestamps for ML causal-correctness + point-in-time
            -- replay (Holden D2 PM call; see migration docstring for
            -- per-column semantics).
            event_occurred_at     TIMESTAMPTZ  NULL,
            source_published_at   TIMESTAMPTZ  NOT NULL,
            ingested_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
            valid_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),
            valid_until           TIMESTAMPTZ  NULL,
            created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            -- updated_at NULLABLE per V2.42 sub-amendment A convention;
            -- the BEFORE UPDATE trigger (installed below) maintains
            -- freshness on every UPDATE including FK-NULL cascades.
            updated_at            TIMESTAMPTZ  NULL,

            -- Composite PK includes the partition key (PG semantics).
            PRIMARY KEY (id, ingested_at),

            -- Composite UNIQUE for dedup.  ingested_at is part of the
            -- key because PG requires the partition column in every
            -- UNIQUE on a partitioned parent.  Dedup contract is
            -- "within a single partition window."
            CONSTRAINT uq_canonical_observations_dedup
                UNIQUE (source_id, payload_hash, ingested_at),

            -- observation_kind 6-value vocabulary CHECK.
            -- Pattern 73 SSOT mirror of constants.py OBSERVATION_KIND_VALUES.
            CONSTRAINT ck_canonical_observations_kind
                CHECK (observation_kind IN (
                    'game_state', 'weather', 'poll', 'econ',
                    'news', 'market_snapshot'
                )),

            -- Clock-skew guard: source_published_at MUST NOT be more
            -- than 5 minutes ahead of ingested_at.  See migration docstring
            -- for the full Miles operational-feasibility rationale.
            CONSTRAINT ck_canonical_observations_clock_skew
                CHECK (source_published_at <= ingested_at + interval '5 minutes'),

            -- Bitemporal validity well-formedness.
            CONSTRAINT ck_canonical_observations_validity
                CHECK (valid_until IS NULL OR valid_until >= valid_at)
        )
        PARTITION BY RANGE (ingested_at)
        """
    )

    # =========================================================================
    # Four monthly partitions covering session 86-90 soak window.
    #
    # Operators extend forward via ``CREATE TABLE
    # canonical_observations_YYYY_MM PARTITION OF canonical_observations
    # FOR VALUES FROM ('YYYY-MM-01') TO ('YYYY-(MM+1)-01')`` per the
    # operator runbook.  Slot 0078 ships the baseline 4 months; future
    # months are operational, not migration-scope (a tiny migration to
    # extend coverage is acceptable too — both shapes are append-only-
    # safe).
    # =========================================================================
    for partition_name, lower_bound, upper_bound in _INITIAL_PARTITIONS:
        op.execute(
            f"""
            CREATE TABLE {partition_name} PARTITION OF canonical_observations
                FOR VALUES FROM ('{lower_bound}') TO ('{upper_bound}')
            """
        )

    # =========================================================================
    # Five indexes on the partitioned parent (PG12+ propagates to partitions).
    #
    # Index DDL pinned in _INDEX_DEFINITIONS module-level tuple as the
    # Pattern 73 SSOT canonical home — integration test parametrize shares
    # the same names + partial-WHERE shapes.
    # =========================================================================
    for _, index_ddl in _INDEX_DEFINITIONS:
        op.execute(index_ddl)

    # =========================================================================
    # BEFORE UPDATE trigger using slot 0076's generic set_updated_at().
    #
    # Naming: trg_<table>_updated_at per slot 0076 retrofit precedent
    # (verified against 0076_set_updated_at_generic.py).  The function
    # ``set_updated_at()`` already exists from slot 0076; slot 0078 only
    # installs the trigger instance pointing at it.
    #
    # Trigger on the parent table propagates semantics to all partitions
    # automatically (PG behavior since PG12).
    # =========================================================================
    op.execute(
        """
        CREATE TRIGGER trg_canonical_observations_updated_at
            BEFORE UPDATE ON canonical_observations
            FOR EACH ROW
            EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    """Reverse 0078: drop trigger + 5 indexes + 4 partitions + parent table.

    Drop order (mirrors upgrade() in reverse for object-dependency safety):

        1. BEFORE UPDATE trigger (no children depend on it).
        2. Five indexes on the parent table.
        3. Four monthly partitions (DETACH not required — DROP TABLE on a
           partition is direct).
        4. Parent ``canonical_observations`` table.

    ``IF EXISTS`` used throughout for idempotent rollback per session 59
    ``feedback_idempotent_migration_drops.md``.  Re-running downgrade on a
    partially-rolled-back DB is a no-op rather than a crash.

    The downgrade is intentionally lossy: any observation rows in the
    partitions are discarded.  This is by design; upgrade-then-downgrade-
    then-upgrade is the supported cycle (round-trip CI gate per PR #1081),
    not downgrade-and-keep-running on a populated production DB.  Cohort 4
    feature flag stays ``false`` until session 87 soak begins, so at slot
    0078 deploy time partitions are empty and the downgrade is loss-free.
    """
    # Step 1: trigger first (no dependents).
    op.execute(
        "DROP TRIGGER IF EXISTS trg_canonical_observations_updated_at ON canonical_observations"
    )

    # Step 2: indexes (DROP INDEX targets the partitioned-parent index;
    # PG cascades to per-partition index instances automatically).
    for index_name, _ in _INDEX_DEFINITIONS:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")

    # Step 3: drop the 4 monthly partitions (in reverse order for
    # consistency, though PG doesn't care).
    for partition_name, _, _ in reversed(_INITIAL_PARTITIONS):
        op.execute(f"DROP TABLE IF EXISTS {partition_name}")

    # Step 4: parent table.
    op.execute("DROP TABLE IF EXISTS canonical_observations")
