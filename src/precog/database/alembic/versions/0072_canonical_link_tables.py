"""Cohort 3 second slot — ``canonical_market_links`` + ``canonical_event_links``.

Lands the two parallel-shape link tables that bridge the canonical-identity
tier (``canonical_markets`` from Migration 0069 / ``canonical_events`` from
Migration 0067) to the platform-tier rows (``markets`` / ``events``) under a
state machine governed by ``link_state IN ('active','retired','quarantined')``.
The single load-bearing schema invariant of Cohort 3 ships in this slot: a
partial EXCLUDE constraint that admits at most one ``link_state = 'active'``
row per platform-row id.

Per session-78 user-adjudicated 5-slot Cohort 3 mapping (synthesis E1) +
Cohort 3 design council L12-L13 (parallelism IS the contract; ship lockstep)
this migration ships BOTH link tables in a single slot.  Slot 0073's
``canonical_match_log`` follows; slot 0074's review/override tables follow;
slot 0075's ``observation_source`` registry closes Cohort 3.

Scope of 0072 (two tables, four FK-target indexes, two BEFORE UPDATE triggers,
two trigger functions, two EXCLUDE-USING-btree partial-active constraints):

    1. ``canonical_market_links`` (link table) — canonical_market <-> platform
       market, single-active-link-per-platform-market invariant.  Surrogate
       BIGSERIAL PK so child rows in slot 0073's ``canonical_match_log.link_id``
       and slot 0074's ``canonical_match_reviews.link_id`` can FK into it.
    2. ``canonical_event_links`` (link table) — canonical_event <-> platform
       event, single-active-link-per-platform-event invariant.  Same shape as
       (1) with ``canonical_market_id`` → ``canonical_event_id`` and
       ``platform_market_id`` → ``platform_event_id`` substitutions.

Polarity asymmetry on the FK ON DELETE rules (L3 + L4):

    Canonical-tier FK (RESTRICT):
        ``canonical_market_id`` REFERENCES ``canonical_markets(id)``
            ``ON DELETE RESTRICT`` — symmetry with Cohort 2 decision #5b.
            Settlement-bearing canonical markets must not silently lose their
            platform-link audit trail when a canonical row is dropped.  RESTRICT
            forces operators to retire links first.
        ``canonical_event_id`` REFERENCES ``canonical_events(id)`` likewise.

    Platform-tier FK (CASCADE):
        ``platform_market_id`` REFERENCES ``markets(id)`` ``ON DELETE CASCADE``.
        ``platform_event_id`` REFERENCES ``events(id)`` likewise.  When a
        platform row disappears (rare; usually an external import-pipeline
        re-key), its link rows become meaningless — CASCADE the dead link
        out.  Surviving audit trail of the matching decision is the slot-0073
        ``canonical_match_log``'s job, NOT this table's; that decoupling is
        why ``canonical_match_log.link_id ON DELETE SET NULL`` per ADR-118
        v2.42 sub-amendment B.

Pattern 81 (lookup convention) — N/A carve-out for ``link_state``:

    ``link_state VARCHAR(16) NOT NULL CHECK (link_state IN
    ('active','retired','quarantined'))`` is intentionally NOT a Pattern 81
    lookup table (closed enum; every value binds to code branches per Pattern
    81 § "When NOT to Apply").  Adding a new state requires a code deploy
    regardless of where the vocabulary lives.  Builder-side carve-out is
    explicit so a future "consistency cleanup" PR proposing a
    ``canonical_link_states`` lookup table fails design review at the
    docstring-of-this-migration level.

    ✅ Pattern 81 lookup FK ``algorithm_id`` → ``match_algorithm(id)``: the
    canonical Pattern 81 instance (Migration 0071, slot 0071).  Open
    algorithm-name set encoded in the lookup table; this migration FKs into it.

Pattern 73 (SSOT) — ✅ for ``LINK_STATE_VALUES`` constant:

    The canonical Python source-of-truth for ``link_state`` values lives at
    ``src/precog/database/constants.py`` as ``LINK_STATE_VALUES``.  Both link
    tables' inline CHECK constraints carry a SQL-comment pointer to that
    constant.  CRUD modules + tests + future state-machine code MUST import
    from the constants module — never hardcode the string list — per
    CLAUDE.md Critical Pattern #8.

Pattern 84 (NOT VALID + VALIDATE for CHECK on populated tables) — N/A:

    Fresh empty tables; ``canonical_market_links`` and ``canonical_event_links``
    don't exist before this migration.  No seed paths; the first row in either
    table is written by Cohort 5+ matcher code at runtime.  Per Pattern 84 §
    "When NOT to Apply" both criteria met:

        * Zero rows in dev/staging at migration time (tables don't exist yet).
        * No expected rows by production deploy time (no seeds; populated by
          Cohort 5+ runtime code).

    Documented here so a future PR proposing "two-phase NOT VALID + VALIDATE
    on these CHECKs" can be rejected at review.

Pattern 87 (Append-only migrations) — ✅ reaffirmed:

    DEVELOPMENT_PATTERNS V1.40 (PR #1080).  Slot 0072 is a NEW migration; the
    pattern fires when editing PREVIOUSLY-MERGED migrations.  This PR makes
    ZERO edits to migrations 0001-0071.  Stale forward-references in shipped
    migrations 0067-0071 (e.g., "Migration 0072 ships canonical_market_links"
    is now correct, but earlier slot-mapping wording elsewhere may be stale)
    are corrected via ADR amendment, never by editing the shipped migration.

EXCLUDE invariant — the single load-bearing Cohort 3 contract (L6 + L7):

    ``CONSTRAINT uq_canonical_market_links_active EXCLUDE USING btree
    (platform_market_id WITH =) WHERE (link_state = 'active')`` — partial
    EXCLUDE constraint; only ONE row per ``platform_market_id`` may have
    ``link_state = 'active'``.  Retired/quarantined rows coexist freely (a
    single platform market may have arbitrarily many historical retired
    links, plus zero or one active link, plus arbitrarily many quarantined
    links).

    Holden H:18-21 (session 78 design council): "the single biggest schema-
    safety risk in the entire canonical layer is link uniqueness leakage."
    The whole reason the canonical tier exists is to answer "what is the
    canonical identity of this platform row?" — if two active links can
    coexist for the same platform_market_id, that question resolves to
    arbitrary results depending on JOIN ordering and the canonical layer
    fails its core contract.

    The integration test for this invariant is mandatory and load-bearing:
    insert two ``active`` rows with the same ``platform_market_id``, assert
    ``psycopg2.errors.ExclusionViolation`` (NOT generic ``IntegrityError``).
    Same load-bearing test on ``canonical_event_links`` per L13 (parallelism
    IS the contract).

BEFORE UPDATE trigger pattern (L19 carry-forward from Migration 0069):

    Two per-table inline trigger functions:
        ``update_canonical_market_links_updated_at()``
        ``update_canonical_event_links_updated_at()``

    Body (identical in both): ``NEW.updated_at = now(); RETURN NEW;``  Per
    Cohort 2 v2.39 template; the generic ``set_updated_at()`` retrofit is
    queued for slot 0076+ (ADR-118 v2.42 sub-amendment A / Issue #1074); slot
    0072 ships per-table inline functions that the future generic-retrofit
    migration will absorb.  The function-naming convention ``update_<table>_
    updated_at`` is per session-73 Glokta + Ripley convergent finding (per-
    table for grep-ability + OR-REPLACE aliasing safety).

S82 Builder considerations — documentation-discipline only (no DDL change):

    Four S82 considerations from Miles + Uhura land in this migration's
    docstring per the build spec § 6.

    Consideration #1 — Maintenance ownership (Miles):
        No row archival ships in Cohort 3.  The ``retired_at`` column +
        EXCLUDE partial-active index keep the working set bounded by
        platform-row count regardless of total row count, but total row
        growth has no cap.  Retired-row archival on ``canonical_market_links``
        and ``canonical_event_links`` is Cohort 7+ when scale evidence
        justifies.  Sister table ``canonical_match_log`` (slot 0073) is
        append-only with no Cohort-3 archival per L36 + Elrond E:86.

    Consideration #2 — Scheduling ownership (Miles):
        No triggers ship in slot 0072 BEYOND the BEFORE UPDATE per-row
        ``updated_at`` maintenance trigger.  Retirement, review-creation,
        and audit-log writes are Cohort 5+ application-layer responsibilities
        owned by ``src/precog/matching/`` resolver code.  Trigger-enforcement
        of the append-only invariant on ``canonical_match_log`` is a Cohort
        8/9 hardening decision contingent on 30-day soak evidence per L10 +
        L38 + Elrond E:90 negative constraint #6.

    Consideration #3 — Two-table-write transactional discipline (Miles):
        Cohort 5+ matcher writes touch BOTH this table (link INSERT) AND
        ``canonical_match_log`` (slot 0073, log INSERT).  The atomicity of
        these two-table writes is enforced at the CRUD layer in a single
        ``BEGIN ... COMMIT`` transaction (named ``create_link_with_log()`` or
        equivalent — defers naming to the Cohort 5+ CRUD bundle).  The schema
        does NOT enforce atomicity via FK cascade or trigger because
        ``canonical_match_log.link_id ON DELETE SET NULL`` (per ADR-118 v2.42
        sub-amendment B) deliberately decouples the lifecycle.  Pattern 73
        SSOT pointer for the CRUD-layer transactional contract is documented
        in slot 0073's ``crud_canonical_match_log.append_match_log_row()``
        API when that lands.

    Consideration #4 — Operator alert query reference catalog (Miles):
        Six canonical operator-alert queries enabled by the columns in this
        slot's tables (and slot 0074's review/override tables).  The matrix
        is the reference catalog for the Cohort 5+ alerting layer; slot-0072
        rows are marked ✅; slot-0074 rows are marked → 0074.

        +-------------------------------+--------------------------------+--------+
        | Alert condition               | Schema columns required        | Slot   |
        +-------------------------------+--------------------------------+--------+
        | Quarantined link surge        | link_state, decided_at         | 0072 ✅|
        | Low-confidence cluster        | confidence, decided_at         | 0072 ✅|
        | Algorithmic divergence        | algorithm_id, link_state,      | 0072 ✅|
        |                               | decided_at                     |        |
        | Unmatched-platform backlog    | (NOT NULL FK absence semantics |        |
        |                               | via LEFT JOIN to markets/events|        |
        |                               | unmatched filter)              | 0072 ✅|
        | Stale active links            | link_state, decided_at         | 0072 ✅|
        | Override-rate spike           | (canonical_match_overrides     |        |
        |                               | table — slot 0074 territory)   | →0074  |
        +-------------------------------+--------------------------------+--------+

Forward-pointer: slot 0073 build spec carries S82 Considerations #5
(``decided_by`` value-set Pattern 73 SSOT pointer), #6 (v2.42 sub-amendment B
SET NULL canonical query template), #7 (``manual_v1`` algorithm_id-on-override
convention).  This slot's scope ends at the link tables.

Critical Pattern #6 (Immutable Versioning) — N/A:

    Link tables are typed link/relation tables, not entity / strategy / model
    versioning targets.  UPDATE on ``link_state`` (active → retired) is the
    intended path; immutability does not apply.

Critical Pattern #1 (Decimal Precision) — ✅:

    ``confidence NUMERIC(4,3) NOT NULL CHECK (confidence >= 0 AND confidence
    <= 1)``.  PostgreSQL ``numeric`` is the appropriate type for [0,1]-bounded
    probabilities; application code passes through Python ``Decimal``, never
    ``float``, per CLAUDE.md Critical Pattern #1.  CRUD modules document this.

Carry-forward from Cohort 2 (Migration 0069):

    1. Samwise FK-index discipline — ADR omits indexes (per ADR convention),
       migrations always add them because planners use them for joins.  Two
       FK-target indexes per table: one on the canonical-tier FK column, one
       on the algorithm_id FK column (Miles' canonical operator-health "group
       by algorithm_id" alert query).  The platform-tier FK index is supplied
       by the EXCLUDE-USING-btree partial-active constraint's underlying
       index (which covers the ``link_state = 'active'`` predicate; non-
       active platform_id queries hit a sequential scan on small tables
       and degrade gracefully — explicit non-partial index added if scale
       evidence demands per Miles consideration #1).

    2. Per-table inline trigger functions per Cohort 2 amendment decision #4.

Round-trip discipline (S82 Risk G mitigation):

    PR #1066 (round-trip CI gate) ships in this same session.  Slot 0072's
    ``downgrade()`` is a pure inverse of ``upgrade()``: every CREATE in
    upgrade has a matching ``DROP IF EXISTS`` in downgrade.  Drop order
    respects object dependencies (trigger → trigger function → table; child
    table dropped before parent if FK dependency existed, but the two link
    tables have no inter-FK so order is symmetric).  Manual round-trip
    cycle clean before commit per Cohort 1+2+3 precedent.

What slot 0072 deliberately does NOT include (scope fence):

    * No ``create_link()`` CRUD helper.  The matcher (Cohort 5+) writes
      through the two-table-write CRUD wrapper that lives with slot 0073's
      ``canonical_match_log``; slot 0072 ships only read + retire helpers.
    * No additional CHECK constraints beyond what build spec § 3 + § 4
      specify.
    * No additional indexes beyond PK + EXCLUDE partial-active + 2 FK-target
      indexes per table.
    * No seed data — link tables are populated by Cohort 5+ runtime code.
    * No generic ``set_updated_at()`` function — queued for slot 0076+ per
      ADR-118 v2.42 sub-amendment A / Issue #1074.

Revision ID: 0072
Revises: 0071
Create Date: 2026-04-26

Issues: Epic #972 (Canonical Layer Foundation — Phase B.5), #1058 (P41
    design-stage codification — second Cohort 3 builder dispatch under
    Tier 0 + S82, FIRST S82 FIRE)
ADR: ADR-118 v2.40 lines 17707-17717 (canonical DDL anchor); v2.41 amendment
    (Cohort 3 5-slot adjudication, session 78); v2.42 sub-amendments A
    (audit-column convention) + B (ON DELETE SET NULL on
    canonical_match_log.link_id, slot 0073 territory)
Design council: session 78 (Galadriel + Holden + Elrond, 38 LOCKs;
    user-adjudicated via synthesis E1 to 5 slots) + session 80 (Miles +
    Uhura S82 design-stage P41 council, 5 ✅ + 4 ⚠️ + 0 ❌ on the
    9-capability matrix; build spec at
    ``memory/build_spec_0072_pm_memo.md``)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0072"
down_revision: str = "0071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create both link tables + indexes + trigger functions + triggers.

    Two parallel structural mirrors (L12-L13).  The DDL for both tables is
    word-for-word identical with column-name substitutions:

        canonical_market_links            canonical_event_links
        --------------------------------- ---------------------------------
        canonical_market_id               canonical_event_id
        platform_market_id                platform_event_id
        REFERENCES canonical_markets(id)  REFERENCES canonical_events(id)
        REFERENCES markets(id)            REFERENCES events(id)

    Step order:

        1. ``canonical_market_links`` table (CREATE TABLE with inline
           EXCLUDE constraint).
        2. FK-target indexes for ``canonical_market_links``.
        3. Trigger function ``update_canonical_market_links_updated_at()``.
        4. ``trg_canonical_market_links_updated_at`` BEFORE UPDATE trigger.
        5. Steps 1-4 repeated for ``canonical_event_links`` /
           ``update_canonical_event_links_updated_at()`` /
           ``trg_canonical_event_links_updated_at``.

    Steps 1-4 use ``op.execute`` for the EXCLUDE-constraint DDL and the
    trigger-function ``CREATE OR REPLACE FUNCTION`` block (both require raw
    SQL form).  Mirrors slot 0069's `op.execute` style for consistency.
    """
    # =========================================================================
    # canonical_market_links
    #
    # Column-level rationale (Builder docstring obligation per build spec § 3):
    #   - id BIGSERIAL PK: children FK INTO this table (canonical_match_log.
    #     link_id slot 0073, canonical_match_reviews.link_id slot 0074);
    #     BIGSERIAL future-proofs against link-row proliferation.
    #   - canonical_market_id BIGINT NOT NULL REFERENCES canonical_markets(id)
    #     ON DELETE RESTRICT: L3.  Settlement-bearing markets must not silently
    #     disappear; symmetry with canonical_markets.canonical_event_id Cohort 2
    #     decision #5b.
    #   - platform_market_id INTEGER NOT NULL REFERENCES markets(id) ON DELETE
    #     CASCADE: L4.  Intentional polarity asymmetry — platform deletion =
    #     link is meaningless; CASCADE the link out.  Audit trail survival is
    #     canonical_match_log's job (slot 0073), NOT this table's.
    #   - link_state VARCHAR(16) NOT NULL CHECK (link_state IN
    #     ('active','retired','quarantined')): L5.  3-value closed enum;
    #     inline CHECK NOT a Pattern 81 lookup.  Pattern 73 SSOT pointer:
    #     canonical home is src/precog/database/constants.py LINK_STATE_VALUES;
    #     adding a state requires lockstep update to both the constant and
    #     this CHECK.
    #   - confidence NUMERIC(4,3) NOT NULL CHECK (0 <= confidence <= 1): L6.
    #     Width supports 0.000-1.000 with 3 decimals.  Phase 1 manual rows
    #     set confidence = 1.0; Cohort 5+ algorithmic rows compute per-
    #     algorithm.  Decimal-precision per Critical Pattern #1.
    #   - algorithm_id BIGINT NOT NULL REFERENCES match_algorithm(id): L29.
    #     Pattern 81 lookup FK.  Immutability of algorithm rows (L31) means
    #     historical algorithm_id values remain valid forever.
    #   - decided_by VARCHAR(64) NOT NULL: attribution column.  Convention
    #     deferred to slot 0073 build spec per S82 Builder consideration #5
    #     ('human:<username>' / 'service:<service-name>' / 'system:<context>').
    #     CHECK does NOT enforce format (free-text actor field).
    #   - decided_at TIMESTAMPTZ NOT NULL DEFAULT now(): when the current
    #     state was decided.  Drives Monitoring queries (Miles' frame).
    #   - retired_at TIMESTAMPTZ NULL: NULL = active.  Cohort 1+2 retirement-
    #     pattern convention.  Set by application code (CRUD retire_link());
    #     NOT maintained by the BEFORE UPDATE trigger (which only refreshes
    #     updated_at).
    #   - retire_reason VARCHAR(64) NULL: PM-adjudicated Open item A from S82
    #     council (build spec § 1).  ADR DDL line 17715 lists this column;
    #     synthesis Section 4 was a partial extraction.  Operator-readable
    #     retirement rationale (e.g., 'platform_delisted', 'algorithm_
    #     corrected', 'duplicate_canonical') without needing to JOIN to
    #     canonical_match_log.  Free-text NULL — application code populates
    #     on retire; Phase 1 may leave NULL.
    #   - created_at TIMESTAMPTZ NOT NULL DEFAULT now(): ADR-118 v2.42
    #     sub-amendment A canonical convention.
    #   - updated_at TIMESTAMPTZ NOT NULL DEFAULT now(): maintained by the
    #     BEFORE UPDATE trigger below, NOT by application code.
    #   - CONSTRAINT uq_canonical_market_links_active EXCLUDE USING btree
    #     (platform_market_id WITH =) WHERE (link_state = 'active'): L6 + L7.
    #     The load-bearing invariant of Cohort 3 (Holden H:18-21).  Partial
    #     EXCLUDE; only ONE row per platform_market_id may have
    #     link_state = 'active'.  Retired/quarantined rows coexist freely.
    # =========================================================================
    op.execute(
        """
        CREATE TABLE canonical_market_links (
            id                    BIGSERIAL    PRIMARY KEY,
            -- link_state vocabulary canonical home:
            -- src/precog/database/constants.py LINK_STATE_VALUES.
            -- Adding a value requires lockstep update of both the constant
            -- and this CHECK constraint (Pattern 73 SSOT discipline).
            canonical_market_id   BIGINT       NOT NULL REFERENCES canonical_markets(id) ON DELETE RESTRICT,
            platform_market_id    INTEGER      NOT NULL REFERENCES markets(id)            ON DELETE CASCADE,
            link_state            VARCHAR(16)  NOT NULL CHECK (link_state IN ('active','retired','quarantined')),
            confidence            NUMERIC(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
            algorithm_id          BIGINT       NOT NULL REFERENCES match_algorithm(id),
            decided_by            VARCHAR(64)  NOT NULL,
            decided_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            retired_at            TIMESTAMPTZ  NULL,
            retire_reason         VARCHAR(64)  NULL,
            created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT uq_canonical_market_links_active
                EXCLUDE USING btree (platform_market_id WITH =) WHERE (link_state = 'active')
        )
        """
    )

    # FK-target indexes (Samwise discipline; planners use them for joins).
    # The platform_market_id partial index is supplied by the EXCLUDE
    # constraint; non-active platform_market_id queries fall back to seq
    # scan and degrade gracefully — explicit non-partial index added when
    # scale evidence justifies (Miles consideration #1).
    op.execute(
        "CREATE INDEX idx_canonical_market_links_canonical_market_id "
        "ON canonical_market_links (canonical_market_id)"
    )
    op.execute(
        "CREATE INDEX idx_canonical_market_links_algorithm_id "
        "ON canonical_market_links (algorithm_id)"
    )

    # BEFORE UPDATE trigger function — per-table inline body per L19 +
    # session-73 Glokta + Ripley convention.  Generic set_updated_at()
    # retrofit queued for slot 0076+ (Issue #1074).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_canonical_market_links_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_canonical_market_links_updated_at
            BEFORE UPDATE ON canonical_market_links
            FOR EACH ROW
            EXECUTE FUNCTION update_canonical_market_links_updated_at()
        """
    )

    # =========================================================================
    # canonical_event_links
    #
    # Parallel structural mirror of canonical_market_links per L12-L13.
    # Substituted columns: canonical_market_id → canonical_event_id;
    # platform_market_id → platform_event_id; markets(id) → events(id).
    # Everything else identical including the EXCLUDE invariant shape, the
    # confidence CHECK, and the trigger pattern.
    #
    # Parallelism IS the contract per L12-L13: without it the canonical layer
    # cannot answer "what's the canonical_event for this Kalshi event row?"
    # symmetrically with "what's the canonical_market for this Kalshi market
    # row?"
    # =========================================================================
    op.execute(
        """
        CREATE TABLE canonical_event_links (
            id                    BIGSERIAL    PRIMARY KEY,
            -- link_state vocabulary canonical home:
            -- src/precog/database/constants.py LINK_STATE_VALUES (shared
            -- with canonical_market_links).
            canonical_event_id    BIGINT       NOT NULL REFERENCES canonical_events(id) ON DELETE RESTRICT,
            platform_event_id     INTEGER      NOT NULL REFERENCES events(id)           ON DELETE CASCADE,
            link_state            VARCHAR(16)  NOT NULL CHECK (link_state IN ('active','retired','quarantined')),
            confidence            NUMERIC(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
            algorithm_id          BIGINT       NOT NULL REFERENCES match_algorithm(id),
            decided_by            VARCHAR(64)  NOT NULL,
            decided_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            retired_at            TIMESTAMPTZ  NULL,
            retire_reason         VARCHAR(64)  NULL,
            created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT uq_canonical_event_links_active
                EXCLUDE USING btree (platform_event_id WITH =) WHERE (link_state = 'active')
        )
        """
    )

    op.execute(
        "CREATE INDEX idx_canonical_event_links_canonical_event_id "
        "ON canonical_event_links (canonical_event_id)"
    )
    op.execute(
        "CREATE INDEX idx_canonical_event_links_algorithm_id "
        "ON canonical_event_links (algorithm_id)"
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_canonical_event_links_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_canonical_event_links_updated_at
            BEFORE UPDATE ON canonical_event_links
            FOR EACH ROW
            EXECUTE FUNCTION update_canonical_event_links_updated_at()
        """
    )


def downgrade() -> None:
    """Reverse 0072: drop both triggers + both functions + all indexes + both tables.

    Drop order (object dependencies dictate the sequence):

        1. ``trg_canonical_event_links_updated_at`` and
           ``trg_canonical_market_links_updated_at`` — depend on their respective
           functions AND their respective tables.  Drop first so functions and
           tables can be dropped cleanly.
        2. ``update_canonical_event_links_updated_at()`` and
           ``update_canonical_market_links_updated_at()`` — depend on nothing
           after the triggers are gone.  Drop next.
        3. FK-target indexes — explicit drop for clarity (DROP TABLE would
           cascade them, but explicit DROP keeps the downgrade readable and
           matches Migration 0069 convention).
        4. ``canonical_event_links`` and ``canonical_market_links`` — leaf
           tables.  Drop last.  Order between them does not matter (no
           inter-FK between the two link tables).

    ``IF EXISTS`` used throughout for idempotent rollback per session 59
    ``feedback_idempotent_migration_drops.md``.  Re-running the downgrade on
    a partially-rolled-back DB is a no-op rather than a crash.

    The downgrade is intentionally lossy: any 0073+ migration that FKs
    ``canonical_market_links.id`` or ``canonical_event_links.id`` (e.g.,
    ``canonical_match_log.link_id``) will fail to apply on a downgraded DB
    until 0072 is re-applied.  This is by design; upgrade-then-downgrade-
    then-upgrade is the supported cycle (round-trip CI gate per PR #1066),
    not downgrade-and-keep-running.
    """
    # canonical_event_links teardown
    op.execute(
        "DROP TRIGGER IF EXISTS trg_canonical_event_links_updated_at ON canonical_event_links"
    )
    op.execute("DROP FUNCTION IF EXISTS update_canonical_event_links_updated_at()")
    op.execute("DROP INDEX IF EXISTS idx_canonical_event_links_algorithm_id")
    op.execute("DROP INDEX IF EXISTS idx_canonical_event_links_canonical_event_id")
    op.execute("DROP TABLE IF EXISTS canonical_event_links")

    # canonical_market_links teardown
    op.execute(
        "DROP TRIGGER IF EXISTS trg_canonical_market_links_updated_at ON canonical_market_links"
    )
    op.execute("DROP FUNCTION IF EXISTS update_canonical_market_links_updated_at()")
    op.execute("DROP INDEX IF EXISTS idx_canonical_market_links_algorithm_id")
    op.execute("DROP INDEX IF EXISTS idx_canonical_market_links_canonical_market_id")
    op.execute("DROP TABLE IF EXISTS canonical_market_links")
