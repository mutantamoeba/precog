"""Cohort 3 third slot — ``canonical_match_log`` audit ledger.

Lands the append-only audit ledger for the matching layer.  Every match
decision in the system (``link`` / ``unlink`` / ``relink`` / ``quarantine``
on the link tables, plus ``override`` / ``review_approve`` /
``review_reject`` on slot-0074's review/override tables) writes one row
here.  This is THE forever-record of who decided what, when, with what
algorithm, against what canonical and platform-tier identities.

Per session-78 user-adjudicated 5-slot Cohort 3 mapping (synthesis E1) +
session-80 S82 design-stage P41 council outcome on slot 0072 + session-81
PM-composed build spec at ``memory/build_spec_0073_pm_memo.md`` (Holden
re-engagement GO-WITH-NOTES; all 3 amendments applied).

Slot 0073 ships ONE table (``canonical_match_log``), 4 indexes, ZERO
triggers, and ZERO trigger functions.  The append-only invariant is
enforced by **application discipline**, not by a trigger: the only
sanctioned write path is the restricted CRUD function
``crud_canonical_match_log.append_match_log_row()``, which exposes no
UPDATE / DELETE / UPSERT API at all.  Trigger-enforced append-only is
queued for slot 0090 after a 30-day soak period validates the application-
discipline approach (per L10 + Cohort 3 design council Elrond E:90 +
build spec § 2 design notes).

Append-only via application discipline (build spec § 2 — design note 1):

    The ledger has NO ``BEFORE INSERT OR UPDATE OR DELETE`` trigger.  No
    ``RAISE EXCEPTION`` on UPDATE / DELETE.  Direct UPDATE/DELETE SQL run
    by hand or by a future code path WOULD succeed at the DB level.  The
    discipline is:

        1. ``crud_canonical_match_log.py`` exposes EXACTLY ONE write
           function: ``append_match_log_row()``.
        2. There are NO ``update_*`` / ``delete_*`` / ``upsert_*``
           functions in the CRUD module.
        3. The CRUD module's docstring loudly forbids ad-hoc UPDATE/DELETE
           SQL touching this table (Pattern 73 violation — drift across
           consumers).
        4. Code review enforces the discipline; future grep audits (S81)
           sweep for direct ``UPDATE canonical_match_log`` / ``DELETE FROM
           canonical_match_log`` SQL outside this migration's downgrade.

    The trigger-enforced version (BEFORE UPDATE/DELETE → ``RAISE EXCEPTION
    'canonical_match_log is append-only'``) is queued for slot 0090 after
    a 30-day production soak validates that the application-discipline
    approach is sufficient.  Forward-pointer in the CRUD module docstring
    makes the future enforcement layer discoverable.

Pattern 73 (SSOT) — ✅ for ``ACTION_VALUES`` + ``DECIDED_BY_PREFIXES``:

    The 7-value ``action`` vocabulary lives at ``src/precog/database/
    constants.py:ACTION_VALUES``; the inline CHECK on this table cites
    that constant by name (Pattern 81 non-application — DDL CHECK + Python
    constant must update in lockstep).  The ``decided_by`` value-set
    convention (3-prefix actor taxonomy) lives at
    ``src/precog/database/constants.py:DECIDED_BY_PREFIXES``; CHECK cannot
    enforce free-text format, so the constant + the CRUD-layer
    real-guard validation in ``append_match_log_row()`` are the
    discipline (Pattern 81 non-application territory and overkill for a
    free-text actor field).

    This migration also implements the **#1085 finding #2 strengthening**
    by spec: the CRUD module imports both constants and uses them in
    real-guard ``ValueError``-raising validation, NOT side-effect-only
    ``# noqa: F401`` imports.  Slot 0072's ``LINK_STATE_VALUES`` import
    convention is intentionally upgraded for slot 0073's ``ACTION_VALUES``
    — the side-effect-only convention does not survive into the new slot.

Pattern 81 (lookup convention) — N/A carve-out for ``action``:

    ``action VARCHAR(16) NOT NULL CHECK (action IN ('link', 'unlink',
    'relink', 'quarantine', 'override', 'review_approve',
    'review_reject'))`` is intentionally NOT a Pattern 81 lookup table.
    The action set is closed (every value binds to code branches per
    Pattern 81 § "When NOT to Apply"); adding a new action requires a
    code deploy regardless of where the vocabulary lives.

    Decided-by prefix taxonomy is similarly closed (3 actor categories);
    Pattern 81 also non-applies there.  Builder-side carve-out is explicit
    so a future "consistency cleanup" PR proposing
    ``canonical_match_log_actions`` or ``canonical_match_log_decider_kinds``
    lookup tables fails design review at the docstring-of-this-migration
    level.

    ✅ Pattern 81 lookup FK ``algorithm_id`` → ``match_algorithm(id)``:
    inherited from slot 0072 + slot 0071 (the canonical Pattern 81
    instance).  Open algorithm-name set encoded in the lookup table.

Pattern 84 (NOT VALID + VALIDATE for CHECK on populated tables) — N/A:

    Fresh empty table; ``canonical_match_log`` does not exist before this
    migration.  No seed paths; the first row in the table is written by
    Cohort 5+ matcher code at runtime via the
    ``append_match_log_row()`` CRUD function.  Per Pattern 84 § "When NOT
    to Apply" both criteria met:

        * Zero rows in dev/staging at migration time (table doesn't
          exist yet).
        * No expected rows by production deploy time (no seeds; populated
          by Cohort 5+ runtime code).

    Documented here so a future PR proposing "two-phase NOT VALID +
    VALIDATE on these CHECKs" can be rejected at review.

Pattern 87 (Append-only migrations) — ✅ reaffirmed:

    DEVELOPMENT_PATTERNS V1.40 (PR #1080).  Slot 0073 is a NEW migration;
    Pattern 87 fires when editing PREVIOUSLY-MERGED migrations.  This PR
    makes ZERO edits to migrations 0001-0072.  Stale forward-references
    in shipped migrations 0067-0072 (e.g., "slot 0073 ships
    canonical_match_log" forward-pointers) are correct as-of this PR;
    any drift surfacing later is corrected via ADR amendment, never by
    editing a shipped migration.

FK polarity rationale (build spec § 2):

    ``link_id BIGINT REFERENCES canonical_market_links(id) ON DELETE SET
    NULL`` (v2.42 sub-amendment B):

        Audit history outlives link deletion.  When a link row is hard-
        deleted (rare; usually a test-cleanup path or a downgrade of
        slot 0072 in a development DB), the log rows that referenced it
        survive with ``link_id = NULL``.  The ``(platform_market_id,
        canonical_market_id, decided_at, decided_by, algorithm_id)``
        tuple still anchors the attribution.

    ``platform_market_id INTEGER NOT NULL`` (L9, deliberately NO FK):

        The audit log outlives the platform row.  Platform rows can be
        re-keyed by external import-pipelines (CASCADE on ``markets`` is
        the slot-0072 link-table policy); when that happens the log row
        survives intact with full attribution preserved.  The L9
        framing: "the log is the truth of who decided what; the platform
        row is a lookup target that may legitimately disappear."  DO NOT
        add an FK here without an ADR amendment + audit-log retention
        policy review — the intent is deliberate.

    ``canonical_market_id BIGINT REFERENCES canonical_markets(id) ON DELETE
    SET NULL``:

        Holden re-engagement P1 catch (memo:
        ``holden_reengagement_0073_memo.md``).  ADR DDL line 17725 listed
        ``canonical_market_id BIGINT`` with NO ON DELETE clause; the
        synthesis Section 4 transcribed the silence.  PostgreSQL defaults
        to ``NO ACTION`` when ON DELETE is unspecified, which would
        silently block ``DELETE FROM canonical_markets`` while audit log
        history references exist — exact failure mode v2.42 sub-amendment
        B was filed to close on ``canonical_events`` FKs.  Slot 0073
        explicitly chooses ``ON DELETE SET NULL`` for symmetry with
        ``link_id`` audit-survival semantics.  DO NOT relax to NO ACTION
        without an ADR amendment + audit-log retention policy review.

    ``algorithm_id BIGINT NOT NULL REFERENCES match_algorithm(id)`` (L29-
    L31):

        Every log row has an algorithm pointer.  The ``manual_v1``
        algorithm row (seeded in Migration 0071) is the placeholder for
        human-decided overrides per the manual_v1-on-override convention
        (E8 + Uhura S82 Builder consideration #7).  See § "manual_v1
        convention" below.

    ``prior_link_id BIGINT REFERENCES canonical_market_links(id) ON DELETE
    SET NULL``:

        For ``action='relink'`` and ``action='unlink'`` rows: pointer to
        the predecessor link row (the row that was retired before the
        current row was created).  ``ON DELETE SET NULL`` is **DELIBERATE
        SPEC-STRENGTHENING beyond the ADR DDL** which left this column
        FK-less; mirrors ``link_id``'s survival semantics by design
        symmetry.  Holden re-engagement P3 caught the implicit
        elaboration; this docstring makes the spec-strengthening explicit
        so a future reader doesn't mistake it for copy-paste from
        ``link_id``.  Both columns share v2.42 sub-amendment B's audit-
        survival semantics by parallel application of the same rule.

manual_v1 algorithm_id-on-override convention (E8 + Uhura S82 Builder
consideration #7):

    Override rows in canonical_match_log have ``action='override'`` and
    ``algorithm_id = manual_v1.id`` (the row seeded by Migration 0071).
    This is a **CATEGORY-FIT CONVENTION**, not a fact:

        - Overrides are human-decided; ``decided_by='human:<username>'``
          carries the actual actor identity.
        - ``algorithm_id`` is NOT NULL on canonical_match_log; we use the
          ``manual_v1`` placeholder so future-log-readers can still JOIN
          to ``match_algorithm`` for category metadata (e.g., to surface
          "this row was a manual decision" via ``algorithm.category =
          'manual'``).
        - Future log-readers MUST NOT mistake
          ``algorithm_id = manual_v1.id`` on ``action='override'`` rows
          for "the manual_v1 algorithm decided this override."  The
          ``decided_by`` column is the source-of-truth for actor
          identity.

    This convention is enforced by the matching layer (Cohort 5+
    application code); the schema itself does not constrain it (cannot —
    ``algorithm_id`` is NOT NULL but the convention is policy-level, not
    schema-level).

decided_by value-set convention (Uhura S82 Builder consideration #5,
Pattern 73 SSOT pointer):

    The canonical home for ``decided_by`` string-format conventions is
    ``src/precog/database/constants.py:DECIDED_BY_PREFIXES``.  CHECK
    constraint cannot enforce free-text format (string-format validation
    is Pattern 81 non-application territory and overkill for a free-text
    actor field); the Pattern 73 pointer + CRUD-layer validation in
    ``append_match_log_row()`` prevent drift.

    Conventions (canonical, redundant cite for grep-discoverability):
        ``'human:<username>'``    — human-driven action
        ``'service:<svc-name>'``  — autonomous matcher service
        ``'system:<context>'``    — seed/migration/system writes

v2.42 sub-amendment B canonical query template (Uhura S82 Builder
consideration #6):

    Operator runbook query: "find all log rows for platform_market X
    including post-link-delete (orphan) rows."

    -- Why: link_id is ON DELETE SET NULL (v2.42 sub-amendment B).  After
    -- a link is deleted, log rows survive with link_id=NULL but full
    -- attribution preserved in (platform_market_id, canonical_market_id,
    -- decided_at, decided_by, algorithm_id).  A naive INNER JOIN on
    -- link_id silently drops the historical orphans; the canonical
    -- approach uses platform_market_id directly (which has no FK and
    -- cannot go NULL on link deletion).
    --
    -- SELECT *
    -- FROM canonical_match_log
    -- WHERE platform_market_id = $1
    --   AND action IN ('link', 'unlink', 'relink', 'quarantine')
    -- ORDER BY decided_at DESC;
    --
    -- The parallel CRUD helper ``get_match_log_for_link(link_id,
    -- include_orphans=True)`` surfaces the orphan-aware query through
    -- the link_id projection, but the platform_market_id-keyed query
    -- above is the canonical operator-facing form.

S82 Builder considerations #5-#7 — landing in this slot per build spec
§ 5: items 5a (decided_by Pattern 73 SSOT pointer), 5b (v2.42 sub-amendment
B canonical query template), 5c (manual_v1 algorithm_id-on-override
convention) all encoded in this migration's docstring above + repeated in
the ``crud_canonical_match_log.py`` module docstring per Pattern 73 SSOT
(canonical home + pointer; never duplicate the rule itself).

Critical Pattern #1 (Decimal Precision) — ✅:

    ``confidence NUMERIC(4,3)`` (NULLABLE, unlike slot 0072 where confidence
    is NOT NULL on the link tables).  Nullable because human overrides
    have no algorithmic confidence — operators don't compute a per-decision
    score; they assert a polarity.  PostgreSQL ``numeric`` is the
    appropriate type for [0,1]-bounded probabilities; application code
    passes through Python ``Decimal``, never ``float``, per CLAUDE.md
    Critical Pattern #1.  CRUD validation accepts ``Decimal | None``.

Critical Pattern #6 (Immutable Versioning) — N/A:

    The audit log is a typed event-stream table, not an entity / strategy
    / model versioning target.  Append-only (via application discipline)
    means there are no UPDATE paths to be immutable about.

Carry-forward from slot 0072 (Migration 0072):

    1. Samwise FK-index discipline — explicit indexes on
       ``platform_market_id``, ``algorithm_id``, and (partial) ``link_id``
       per Holden slot-0073 indexing strategy (4 indexes total including
       ``decided_at DESC``).  Operator audit hot path:
       ``WHERE platform_market_id = X ORDER BY decided_at DESC`` —
       both indexes used together.
    2. ``created_at`` + ``decided_at`` audit-column convention per ADR-118
       v2.42 sub-amendment A; both kept for parity with slot 0072 + slot
       0069 columns even though by convention ``created_at == decided_at``
       on this table (the row's ``decided_at`` is the canonical timestamp
       — when the decision was made — and ``created_at`` records when the
       log row was inserted; these are within microseconds of each other
       for the standard ``append_match_log_row()`` write path).

Round-trip discipline (PR #1081 round-trip CI gate):

    PR #1081 ships the round-trip CI gate as Epic #1071's first slot
    (merged session 80).  Slot 0073's ``downgrade()`` is a pure inverse
    of ``upgrade()``: every CREATE has a matching ``DROP IF EXISTS`` in
    downgrade.  Drop order respects object dependencies (indexes →
    table).  The round-trip gate auto-discovers slot 0073 on push and
    runs ``downgrade -> upgrade head`` against it; no Builder action
    needed beyond clean upgrade/downgrade pairing.

What slot 0073 deliberately does NOT include (scope fence):

    * No append-only enforcement trigger — application-discipline only;
      trigger retrofit queued for slot 0090 after 30-day soak
      (L10 + Elrond E:90 + build spec § 2 design note 1).
    * No ``BEFORE UPDATE`` trigger for ``updated_at`` maintenance —
      append-only tables don't have an ``updated_at`` column at all
      (the ``decided_at`` and ``created_at`` columns are write-once
      by definition).
    * No ``canonical_event_log`` parallel — Cohort 3 ledger is market-
      tier only at this stage (per session-78 LOCK set).  Event-tier
      audit ledger is later cohort scope.
    * No ``update_*`` / ``delete_*`` / ``upsert_*`` CRUD functions; the
      module exposes a single restricted ``append_match_log_row()``
      write path.
    * No seed data — log table is populated by Cohort 5+ matcher code +
      slot 0073 integration test fixtures only.

Revision ID: 0073
Revises: 0072
Create Date: 2026-04-27

Issues: Epic #972 (Canonical Layer Foundation — Phase B.5),
    #1058 (P41 design-stage codification — slot 0073 is the third Cohort
    3 builder dispatch under Tier 0 + S82),
    #1085 (slot-0073 polish-item inheritance from slot-0072 review)
ADR: ADR-118 v2.41 lines 17721-17730 (canonical DDL anchor) +
    v2.42 sub-amendment B (line 17687, link_id ON DELETE SET NULL —
    extended to canonical_market_id by Holden P1 catch on the build spec)
Build spec: ``memory/build_spec_0073_pm_memo.md``
Holden re-engagement: ``memory/holden_reengagement_0073_memo.md``
Design council: session 78 (Galadriel + Holden + Elrond, 38 LOCKs;
    user-adjudicated via synthesis E1 to 5 slots) + session 80 (Miles +
    Uhura S82 design-stage P41 council outcomes inherited from slot 0072)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0073"
down_revision: str = "0072"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create canonical_match_log table + 4 FK-target indexes.

    No triggers ship in this slot.  No trigger functions ship in this
    slot.  Append-only invariant is enforced by the CRUD module's
    restricted API surface (``append_match_log_row()`` only); trigger-
    enforcement is queued for slot 0090 after 30-day soak per L10 +
    Elrond E:90.

    Step order:

        1. ``canonical_match_log`` table (CREATE TABLE with all FK clauses
           + 2 inline CHECK constraints).
        2. ``idx_canonical_match_log_decided_at`` — operator audit hot
           path index (DESC ordering).
        3. ``idx_canonical_match_log_platform_market_id`` — L9 query
           target (the v2.42 SET NULL canonical query template above).
        4. ``idx_canonical_match_log_link_id`` — partial index on
           ``link_id IS NOT NULL`` (most rows post-link-deletion will
           have NULL ``link_id``; the partial form keeps the index small).
        5. ``idx_canonical_match_log_algorithm_id`` — Miles operator-
           alert-query catalog ("group by algorithm_id" health checks).
    """
    # =========================================================================
    # canonical_match_log
    #
    # Column-level rationale (Builder docstring obligation per build spec § 2):
    #   - id BIGSERIAL PK: surrogate.  No child rows FK INTO this table; the
    #     PK exists for direct-row addressability in operator runbooks.
    #   - link_id BIGINT REFERENCES canonical_market_links(id) ON DELETE SET
    #     NULL: v2.42 sub-amendment B.  Audit history outlives link deletion.
    #   - platform_market_id INTEGER NOT NULL: L9.  DELIBERATELY NO FK — log
    #     outlives platform-row CASCADE deletion.  See migration docstring
    #     for the full L9 framing.
    #   - canonical_market_id BIGINT REFERENCES canonical_markets(id) ON DELETE
    #     SET NULL: Holden P1 catch.  Symmetric with link_id audit-survival
    #     semantics; closes the v2.42-trap-repeated failure mode.
    #   - action VARCHAR(16) NOT NULL CHECK (action IN (...)): 7-value closed
    #     enum per session-80 PM adjudication of Open Item B.  Pattern 73 SSOT
    #     pointer: canonical home is src/precog/database/constants.py
    #     ACTION_VALUES; adding a value requires lockstep update to the
    #     constant AND this CHECK.  The crud_canonical_match_log.py module
    #     uses ACTION_VALUES in real-guard validation (NOT side-effect-only
    #     import, per #1085 finding #2 strengthening).
    #   - confidence NUMERIC(4,3) NULL CHECK (0 <= confidence <= 1): nullable
    #     because human overrides have no algorithmic confidence.  Decimal-
    #     precision per Critical Pattern #1.  CHECK uses NULL-tolerant form:
    #     "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)".
    #   - algorithm_id BIGINT NOT NULL REFERENCES match_algorithm(id): L29-L31.
    #     Every log row has an algorithm pointer; manual_v1-on-override
    #     convention covers human-decided rows (see migration docstring).
    #   - features JSONB NULL: free-form input snapshot at decision time.
    #     Schema deferred to Cohort 5+; Phase 1 callers may pass NULL.
    #   - prior_link_id BIGINT REFERENCES canonical_market_links(id) ON DELETE
    #     SET NULL: Holden P3 — DELIBERATE SPEC-STRENGTHENING beyond ADR DDL
    #     which left this column FK-less.  Parallel application of v2.42
    #     sub-amendment B's audit-survival semantics, not copy-paste from
    #     link_id.
    #   - decided_by VARCHAR(64) NOT NULL: actor attribution.  Pattern 73
    #     SSOT pointer to constants.py:DECIDED_BY_PREFIXES.  CHECK does NOT
    #     enforce format (free-text, validated at CRUD boundary).
    #   - decided_at TIMESTAMPTZ NOT NULL DEFAULT now(): canonical decision
    #     timestamp; drives the operator audit hot-path ORDER BY.
    #   - note TEXT NULL: free-text operator-readable explanation.  No
    #     boundary enforcement (TEXT is unbounded by design).
    #   - created_at TIMESTAMPTZ NOT NULL DEFAULT now(): ADR-118 v2.42
    #     sub-amendment A canonical convention.  By convention created_at ==
    #     decided_at on this table (within microseconds for the standard
    #     append_match_log_row() write path).
    #
    # NO updated_at column — this table is append-only; rows are write-once
    # so updated_at would be meaningless (and a "last update" timestamp on an
    # append-only table is a smell that masks an implicit UPDATE path).
    # =========================================================================
    op.execute(
        """
        CREATE TABLE canonical_match_log (
            id                    BIGSERIAL    PRIMARY KEY,
            -- link_id ON DELETE SET NULL per ADR-118 v2.42 sub-amendment B:
            -- audit history outlives link deletion.
            link_id               BIGINT       NULL REFERENCES canonical_market_links(id) ON DELETE SET NULL,
            -- platform_market_id deliberately NO FK (L9): log outlives the
            -- platform row.  Adding an FK here requires an ADR amendment.
            platform_market_id    INTEGER      NOT NULL,
            -- canonical_market_id ON DELETE SET NULL per Holden re-engagement
            -- P1 catch: ADR DDL was silent here; silent-NO-ACTION default
            -- would block canonical_markets DELETE while audit log history
            -- references exist.  Symmetric with link_id audit-survival.
            canonical_market_id   BIGINT       NULL REFERENCES canonical_markets(id) ON DELETE SET NULL,
            -- action vocabulary canonical home:
            -- src/precog/database/constants.py ACTION_VALUES.
            -- Adding a value requires lockstep update of both the constant
            -- AND this CHECK constraint (Pattern 73 SSOT discipline).
            action                VARCHAR(16)  NOT NULL,
            -- confidence nullable because human overrides have no algorithmic
            -- confidence.  CHECK uses NULL-tolerant form.
            confidence            NUMERIC(4,3) NULL,
            -- algorithm_id NOT NULL per L29-L31; manual_v1 placeholder used
            -- for human-decided override rows (E8 + manual_v1-on-override
            -- convention; see migration docstring).
            algorithm_id          BIGINT       NOT NULL REFERENCES match_algorithm(id),
            features              JSONB        NULL,
            -- prior_link_id ON DELETE SET NULL per Holden P3 deliberate
            -- spec-strengthening: parallel application of v2.42 sub-amendment
            -- B audit-survival semantics, not copy-paste from link_id.
            prior_link_id         BIGINT       NULL REFERENCES canonical_market_links(id) ON DELETE SET NULL,
            -- decided_by value-set canonical home:
            -- src/precog/database/constants.py DECIDED_BY_PREFIXES.
            -- CHECK does NOT enforce format (free-text actor field; CRUD-
            -- layer validation in append_match_log_row() is the discipline).
            decided_by            VARCHAR(64)  NOT NULL,
            decided_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            note                  TEXT         NULL,
            created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT ck_canonical_match_log_action CHECK (action IN (
                'link', 'unlink', 'relink', 'quarantine',
                'override', 'review_approve', 'review_reject'
            )),
            CONSTRAINT ck_canonical_match_log_confidence CHECK (
                confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
            )
        )
        """
    )

    # Operator audit hot-path index: ORDER BY decided_at DESC dominates
    # operator runbook queries.  DESC index avoids server-side reverse-
    # scan when paired with ORDER BY decided_at DESC.
    op.execute(
        "CREATE INDEX idx_canonical_match_log_decided_at ON canonical_match_log (decided_at DESC)"
    )

    # L9 query-target index: the v2.42 SET NULL canonical query template
    # filters by platform_market_id (which has no FK and cannot go NULL on
    # link deletion); this index is its primary-access path.
    op.execute(
        "CREATE INDEX idx_canonical_match_log_platform_market_id "
        "ON canonical_match_log (platform_market_id)"
    )

    # Partial index on link_id IS NOT NULL: most rows post-link-deletion
    # carry NULL link_id (v2.42 sub-amendment B SET NULL); the partial form
    # keeps the index small and correct for INNER JOINs that filter NULLs.
    op.execute(
        "CREATE INDEX idx_canonical_match_log_link_id "
        "ON canonical_match_log (link_id) WHERE link_id IS NOT NULL"
    )

    # Miles operator-alert-query catalog: "group by algorithm_id" health
    # checks (low-confidence cluster, algorithmic divergence) and the
    # algorithm-retire flow's "are there log rows still pointing here?"
    # query both depend on this index.
    op.execute(
        "CREATE INDEX idx_canonical_match_log_algorithm_id ON canonical_match_log (algorithm_id)"
    )


def downgrade() -> None:
    """Reverse 0073: drop 4 indexes + the canonical_match_log table.

    Drop order:

        1. Indexes — explicit drop for clarity (DROP TABLE would cascade
           them, but explicit DROP keeps the downgrade readable and
           matches Migration 0072 convention).
        2. ``canonical_match_log`` table — leaf; no child tables FK INTO
           this table at slot 0073, so DROP is unconditionally safe.

    ``IF EXISTS`` used throughout for idempotent rollback per session 59
    ``feedback_idempotent_migration_drops.md``.  Re-running the downgrade
    on a partially-rolled-back DB is a no-op rather than a crash.

    The downgrade is intentionally lossy: the audit ledger contents are
    discarded.  This is by design; upgrade-then-downgrade-then-upgrade is
    the supported cycle (round-trip CI gate per PR #1081), not downgrade-
    and-keep-running on a populated production DB.  Production-tier
    rollback of the audit ledger is out of scope; if a P0 surfaces post-
    merge, the cleanest recovery path is a slot 0074+ reversal migration
    that explicitly preserves the data (Holden Q5 rollback analysis).
    """
    # Indexes first (explicit drop for parity with slot 0072 convention).
    op.execute("DROP INDEX IF EXISTS idx_canonical_match_log_algorithm_id")
    op.execute("DROP INDEX IF EXISTS idx_canonical_match_log_link_id")
    op.execute("DROP INDEX IF EXISTS idx_canonical_match_log_platform_market_id")
    op.execute("DROP INDEX IF EXISTS idx_canonical_match_log_decided_at")

    # Leaf table — no children FK INTO it at slot 0073, so unconditional drop.
    op.execute("DROP TABLE IF EXISTS canonical_match_log")
