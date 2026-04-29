"""Cohort 3 final slot — ``canonical_match_overrides`` + ``canonical_match_reviews``.

**Cohort 3 closes with this slot.**

Lands the two operational-state tables that the matching layer reads
(overrides) and writes (reviews) alongside the audit ledger
(``canonical_match_log``, slot 0073).  Per session-78 user-adjudicated
5-slot Cohort 3 mapping (synthesis E1) + session-80 S82 design-stage
P41 council inheritance + session-82 PM-composed build spec at
``memory/build_spec_0074_pm_memo.md`` (Holden re-engagement
GO-WITH-NOTES; all 4 amendments applied via Tier 1 Momentum).

Slot 0074 ships TWO tables (``canonical_match_reviews`` +
``canonical_match_overrides``), 6 indexes (3 per table), 5 CHECK
constraints, 1 UNIQUE constraint, and ZERO triggers / trigger functions.

Non-monotonic Alembic chain — ``0073 → 0075 → 0074``:

    Slot 0075 (``observation_source``) was sequenced before slot 0074 in
    session 81 because slot 0075 had zero FK dependencies on slot 0074
    while slot 0074 inherits from slot 0073's audit-ledger conventions
    (``manual_v1-on-human-decided-actions`` placeholder; ``algorithm_id``
    NOT NULL discipline; the 7-value ``ACTION_VALUES`` vocabulary).
    Sequencing slot 0075 first let the lookup-foundation work ship in
    parallel with slot 0074's design-verification pipeline (Holden
    re-engagement + Pattern 73 SSOT amendment cycle).  After this slot
    ships, the chain is ``... → 0073 → 0075 → 0074`` linearly; the head
    becomes ``0074`` and Cohort 3 is closed.

    The non-monotonic shape is documented loudly in slot 0075's
    docstring (``memory/build_spec_0075_pm_memo.md`` § 4) AND in this
    migration's ``down_revision = '0075'``.  Future readers tracing the
    chain by file-name-numeric-order will see ``0073 → 0074`` as the
    natural sequence; the runtime authoritative ordering is in the
    ``down_revision`` declarations, not the filename.

Append-only via application discipline (build spec § 2 — N/A this slot):

    Reviews and overrides are NOT append-only tables.  ``transition_review``
    UPDATEs ``canonical_match_reviews`` rows (state machine forward + can-
    revisit transitions per § 4a build spec).  ``delete_override`` hard-
    DELETEs ``canonical_match_overrides`` rows (paired with an audit log
    insert via the ``manual_v1-on-human-decided-actions`` convention).
    The append-only discipline applies only to ``canonical_match_log``
    (slot 0073); these tables are operational-state surfaces.

    Audit trail of operations on these tables IS append-only — every
    create-review, transition-review, create-override, and delete-override
    writes a row to ``canonical_match_log`` (action ∈ {'override',
    'review_approve', 'review_reject'}).  The log is the forever-record;
    these tables are the working set.

Pattern 73 (SSOT) — ✅ for ``REVIEW_STATE_VALUES`` + ``POLARITY_VALUES``:

    Two vocabularies are SSOT-anchored at
    ``src/precog/database/constants.py``:

        ``REVIEW_STATE_VALUES``  — 4-value ``review_state`` discriminator
                                   (pending / approved / rejected /
                                   needs_info).  Inline DDL CHECK on
                                   ``canonical_match_reviews.review_state``
                                   cites this constant by name; the
                                   ``crud_canonical_match_reviews`` module
                                   uses it in REAL-GUARD validation.  Slot
                                   0074 ADDS this constant; before slot
                                   0074 ships the constant is not
                                   referenced anywhere in production code.

        ``POLARITY_VALUES``      — 2-value ``polarity`` vocabulary
                                   (MUST_MATCH / MUST_NOT_MATCH).  Pre-
                                   positioned in slot 0072 per S82 council
                                   Section 4 recommendation; slot 0074
                                   FINALLY uses it in REAL-GUARD validation
                                   inside ``crud_canonical_match_overrides``.

    Per #1085 finding #2 strengthening + slot-0073 precedent: both new
    CRUD modules import + USE the constants in real-guard
    ``ValueError``-raising validation, NOT side-effect-only ``# noqa: F401``
    imports.  The slot-0072 ``LINK_STATE_VALUES`` side-effect-only
    convention does not survive into slot 0074.

Pattern 81 (lookup convention) — N/A carve-out for ``review_state`` +
``polarity``:

    Both vocabularies are intentionally NOT Pattern 81 lookup tables.
    The state sets are closed (every value binds to code branches per
    Pattern 81 § "When NOT to Apply"); adding a new state requires a
    code deploy regardless of where the vocabulary lives.

    Same carve-out rationale as ``LINK_STATE_VALUES`` (slot 0072) /
    ``ACTION_VALUES`` (slot 0073).  Builder-side carve-out is explicit so
    a future "consistency cleanup" PR proposing
    ``canonical_match_review_states`` or ``canonical_match_polarities``
    lookup tables fails design review at the docstring-of-this-migration
    level.

Pattern 84 (NOT VALID + VALIDATE for CHECK on populated tables) — N/A:

    Fresh empty tables; ``canonical_match_reviews`` and
    ``canonical_match_overrides`` do not exist before this migration.
    No seed paths; the first row in either table is written by Cohort 5+
    matcher / operator code at runtime via the slot-0074 CRUD modules.
    Per Pattern 84 § "When NOT to Apply" both criteria met:

        * Zero rows in dev/staging at migration time (tables don't
          exist yet).
        * No expected rows by production deploy time (no seeds; populated
          by Cohort 5+ runtime code).

    Documented here so a future PR proposing "two-phase NOT VALID +
    VALIDATE on these CHECKs" can be rejected at review.

Pattern 87 (Append-only migrations) — ✅ reaffirmed:

    DEVELOPMENT_PATTERNS V1.40 (PR #1080).  Slot 0074 is a NEW migration;
    Pattern 87 fires when editing PREVIOUSLY-MERGED migrations.  This PR
    makes ZERO edits to migrations 0001-0075.  Stale forward-references
    in shipped migrations 0067-0075 (e.g., "slot 0074 ships
    canonical_match_reviews + canonical_match_overrides" forward-pointers)
    are correct as-of this PR; any drift surfacing later is corrected via
    ADR amendment, never by editing a shipped migration.

FK polarity rationale (build spec § 2 + Holden re-engagement § Q1):

    ``canonical_match_reviews.link_id BIGINT REFERENCES
    canonical_market_links(id) ON DELETE CASCADE``:

        Reviews die with their link.  A review row exists to track
        operator review of a specific link's correctness; without the
        link the review is meaningless.  CASCADE the dead reviews out.

        The audit trail for review state transitions is preserved
        elsewhere — every ``transition_review`` to ``approved`` or
        ``rejected`` writes a ``canonical_match_log`` row with
        ``action='review_approve'`` or ``'review_reject'``.  Per slot
        0073's ``link_id ON DELETE SET NULL`` (v2.42 sub-amendment B)
        those log rows survive link deletion via the SET NULL audit-
        survival semantics.  The asymmetry is DELIBERATE: review-table
        rows are operational state (CASCADE); log rows are historical
        record (SET NULL).

    ``canonical_match_overrides.platform_market_id INTEGER REFERENCES
    markets(id) ON DELETE CASCADE``:

        Override dies with the platform market.  Same shape as
        ``canonical_market_links.platform_market_id ON DELETE CASCADE``
        (slot 0072) — when a platform row disappears (rare; usually
        an external import-pipeline re-key), its override becomes
        meaningless and CASCADE removes it.

    ``canonical_match_overrides.canonical_market_id BIGINT NULL REFERENCES
    canonical_markets(id) ON DELETE RESTRICT``:

        DELIBERATE asymmetry vs the audit log's SET NULL.  An override
        row's ``canonical_market_id`` is operationally load-bearing —
        a MUST_MATCH override SAYS "this canonical_market IS the right
        canonical for this platform_market"; if the canonical row
        silently disappeared the override would be left pointing at
        nothing.  RESTRICT forces operators to retire the override
        first via ``delete_override()`` (which writes its own audit log
        row); only then can the canonical row be removed.

        Symmetric with ``canonical_market_links.canonical_market_id ON
        DELETE RESTRICT`` (slot 0072).  Active links AND MUST_MATCH
        overrides are both "human-asserted bindings" requiring
        explicit retire.

        NULLABLE per the polarity discriminator: MUST_NOT_MATCH overrides
        have NO canonical_market_id pointer (the canonical row is
        meaningless when the override SAYS "this platform_market is NOT
        in any canonical group"); the polarity-pairing CHECK enforces
        the NULL/NOT-NULL pairing in three-valued-logic-safe form.

The polarity-pairing CHECK is the load-bearing schema invariant for slot
0074:

    ``CONSTRAINT ck_canonical_match_overrides_polarity_pairing CHECK (
        (polarity = 'MUST_NOT_MATCH' AND canonical_market_id IS NULL)
        OR (polarity = 'MUST_MATCH' AND canonical_market_id IS NOT NULL)
    )``

    Enforces:

        polarity='MUST_NOT_MATCH'  ↔  canonical_market_id IS NULL
        polarity='MUST_MATCH'      ↔  canonical_market_id IS NOT NULL

    WHY: MUST_NOT_MATCH means "this platform_market is NOT in any
    canonical group"; the canonical_market_id pointer is meaningless and
    must be NULL.  MUST_MATCH means "this canonical_market_id IS the
    right canonical for this platform_market"; the pointer is mandatory.

    The CRUD-layer validation in ``create_override()`` raises ValueError
    BEFORE INSERT when the pairing is violated; the DDL CHECK is
    defense-in-depth (catches direct-SQL bypass).  Tests MUST exercise
    BOTH branches (MUST_MATCH with NULL canonical → reject; MUST_NOT_MATCH
    with non-NULL canonical → reject) plus the happy paths.

    Three-valued-logic safety: CHECK uses ``IS NULL`` / ``IS NOT NULL``
    (not ``= NULL`` / ``!= NULL``).  In SQL, ``x = NULL`` is NULL (not
    TRUE), so the CHECK would silently admit any row.  ``IS NULL`` is the
    only correct form here.

The reason-nonempty CHECK is defense-in-depth:

    ``CONSTRAINT ck_canonical_match_overrides_reason_nonempty CHECK (
        length(trim(reason)) > 0
    )``

    The CRUD-boundary validation ``if reason.strip() == "": raise
    ValueError(...)`` is the primary defense (per #1085 finding #7
    inheritance — slot 0072's ``retire_reason=""`` empty-string-acceptance
    pattern); this DDL CHECK catches direct-SQL bypass.  Operators MUST
    supply a non-empty reason; an empty audit trail explanation is
    unacceptable for human-decided overrides.

manual_v1-on-human-decided-actions convention (build spec § 5c, scope-
extended from slot 0073):

    The 7-value ``canonical_match_log.action`` vocabulary partitions into:
        - Algorithm-decided: 'link', 'unlink', 'relink', 'quarantine'
          (Cohort 5+ matcher writes; algorithm_id reflects the deciding
          algorithm)
        - Human-decided: 'override', 'review_approve', 'review_reject'
          (slot 0074+ CRUD writes; algorithm_id = manual_v1.id by
          convention)

    For human-decided actions, ``algorithm_id=manual_v1.id`` is a
    CATEGORY-FIT PLACEHOLDER, not a fact:

        - Overrides + review state transitions are decided by humans
          (``decided_by='human:<username>'``).
        - ``algorithm_id`` is NOT NULL on canonical_match_log; we use the
          ``manual_v1`` placeholder so future-log-readers can still JOIN
          to ``match_algorithm`` for the category metadata ("this row was
          a human decision").
        - Future log-readers MUST NOT mistake ``algorithm_id=manual_v1.id``
          on these action rows for "the manual_v1 algorithm decided this."
          The ``decided_by`` column carries the actual actor identity.

    This convention is enforced by the slot-0074 CRUD modules (which
    resolve ``manual_v1.id`` via lookup and pass it explicitly to
    ``append_match_log_row()``); the schema itself does not constrain it
    (cannot — algorithm_id NOT NULL is a schema invariant; "must equal
    manual_v1.id when action ∈ {override, review_approve, review_reject}"
    is policy-level).

Critical Pattern #1 (Decimal Precision) — N/A:

    Neither table has a Decimal-typed column.  Reviews carry no confidence
    score (the canonical_match_log row paired with the transition does);
    overrides carry no confidence (operators assert polarity, not score).
    Slot 0073's ``confidence NUMERIC(4,3)`` is the only Decimal column in
    the matching ledger.

Critical Pattern #6 (Immutable Versioning) — N/A:

    Reviews are operational-state rows whose ``review_state`` IS the
    state-machine surface; UPDATE (state transitions) is the intended
    path.  Overrides are short-lived operator assertions whose lifecycle
    is INSERT → DELETE (no UPDATE path); ``delete_override()`` is the
    sanctioned removal API.  Neither table is a Pattern 6 versioning
    target.

Carry-forward from slot 0073:

    1. Samwise FK-index discipline — explicit indexes on every FK column
       (``link_id`` on reviews; ``platform_market_id`` covered by UNIQUE
       constraint's underlying index, ``canonical_market_id`` partial
       index on overrides).
    2. ``created_at`` audit-column convention per ADR-118 v2.42
       sub-amendment A; both tables ship ``created_at TIMESTAMPTZ NOT
       NULL DEFAULT now()``.  No ``updated_at`` columns: reviews have
       ``reviewed_at`` (state-transition timestamp; populated by CRUD
       on transition out of 'pending'); overrides are INSERT-then-DELETE
       (no in-place mutation).

    3. Helper-extraction discipline — slot-0074 integration tests reuse
       ``tests/integration/database/_canonical_market_helpers.py`` (PR
       #1092 extraction closing #1089 from slot 0073) rather than
       redefining canonical-market / platform-market / link / algorithm
       seed shapes.

Round-trip discipline (PR #1081 round-trip CI gate):

    PR #1081 ships the round-trip CI gate as Epic #1071's first slot
    (merged session 80).  Slot 0074's ``downgrade()`` is a pure inverse
    of ``upgrade()``: every CREATE has a matching ``DROP IF EXISTS`` in
    downgrade.  Drop order respects object dependencies (indexes →
    table; reviews dropped before overrides only by alphabetical
    convention — neither table FKs into the other).  The round-trip
    gate auto-discovers slot 0074 on push and runs ``downgrade -> upgrade
    head`` against it; no Builder action needed beyond clean upgrade /
    downgrade pairing.

What slot 0074 deliberately does NOT include (scope fence):

    * No trust-tier view (``v_canonical_market_llm``) — Cohort 5+
      LLM-surface scope.
    * No match-decision write paths (the matcher itself + the override /
      review state-machine state-machine code) — Cohort 5+.
    * No ``canonical_event_overrides`` / ``canonical_event_reviews``
      parallels — not in the matching-ledger LOCK set; market-tier only.
    * No append-only enforcement trigger on
      ``canonical_match_log`` — slot 0090 territory after 30-day soak.
    * No seed data — review/override tables are populated by Cohort 5+
      runtime code + slot-0074 integration test fixtures only.

Cohort 3 close-out:

    Slot 0074 closes Cohort 3.  Slot inventory:
        0071 (match_algorithm) → 0072 (link tables) → 0073 (audit ledger)
        → 0075 (observation_source) → 0074 (overrides + reviews).
    5 of 5 slots shipped.  Cohorts 4-9 — NOT YET STARTED per
    ``plan_schema_hardening_arc.md``.

Revision ID: 0074
Revises: 0075
Create Date: 2026-04-28

Issues: Epic #972 (Canonical Layer Foundation — Phase B.5),
    #1058 (P41 design-stage codification — slot 0074 is the fifth and
    final Cohort 3 builder dispatch under Tier 0 + S82),
    #1085 (slot-0074 polish-item inheritance from slots 0072/0073/0075
    reviews; this slot addresses 11 of 19 polish items directly +
    structural-mindset inheritance for the rest)
ADR: ADR-118 v2.41 lines 17732-17749 (canonical DDL anchor for both
    tables) + v2.42 + v2.42 sub-amendment B (slot 0073 FK polarity
    precedent for the audit-trail asymmetry)
Build spec: ``memory/build_spec_0074_pm_memo.md``
Holden re-engagement: ``memory/holden_reengagement_0074_memo.md``
Design council: session 78 (Galadriel + Holden + Elrond, 38 LOCKs;
    user-adjudicated via synthesis E1 to 5 slots) + session 80 (Miles +
    Uhura S82 design-stage P41 council outcomes inherited from slot 0072
    + 7 Builder considerations carried into the slot-0074 build spec)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0074"
down_revision: str = "0075"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create canonical_match_reviews + canonical_match_overrides tables + 6 indexes.

    No triggers ship in this slot.  No trigger functions ship in this
    slot.  Reviews are operational-state rows (CRUD UPDATE on state
    transitions); overrides are INSERT-then-DELETE rows (no in-place
    mutation); neither needs an updated_at trigger.

    Step order:

        1. ``canonical_match_reviews`` table (CREATE TABLE with FK to
           canonical_market_links + 1 inline CHECK constraint).
        2. ``idx_canonical_match_reviews_link_id`` — FK-target index
           per Samwise discipline.
        3. ``idx_canonical_match_reviews_review_state`` — partial
           index on ``review_state = 'pending'`` (operator alert hot path).
        4. ``idx_canonical_match_reviews_reviewed_at`` — partial index
           on ``reviewed_at IS NOT NULL`` ("recent review activity"
           hot path).
        5. ``canonical_match_overrides`` table (CREATE TABLE with FKs to
           markets + canonical_markets, + 4 CHECK constraints + 1 UNIQUE
           constraint).
        6. ``idx_canonical_match_overrides_canonical_market_id`` —
           partial index on ``canonical_market_id IS NOT NULL`` (excludes
           MUST_NOT_MATCH NULL rows).
        7. ``idx_canonical_match_overrides_polarity`` — alert-query hot
           path ("show me all MUST_NOT_MATCH overrides").
        8. ``idx_canonical_match_overrides_created_at`` — recent override
           activity hot path (DESC ordering).
    """
    # =========================================================================
    # canonical_match_reviews
    #
    # Column-level rationale (Builder docstring obligation per build spec § 2):
    #   - id BIGSERIAL PK: surrogate.  No child rows FK INTO this table; the
    #     PK exists for direct-row addressability in operator runbooks +
    #     the transition_review() CRUD path.
    #   - link_id BIGINT NOT NULL REFERENCES canonical_market_links(id) ON
    #     DELETE CASCADE: reviews die with their link (intentional; review
    #     row is meaningless without the link).  Asymmetric vs the audit
    #     log's SET NULL — log keeps the review_approve / review_reject
    #     action rows even after the link goes away.
    #   - review_state VARCHAR(16) NOT NULL CHECK (review_state IN (...)):
    #     4-value closed enum.  Pattern 73 SSOT pointer: canonical home is
    #     src/precog/database/constants.py REVIEW_STATE_VALUES; adding a
    #     state requires lockstep update of both the constant AND this
    #     CHECK.  The crud_canonical_match_reviews.py module uses
    #     REVIEW_STATE_VALUES in real-guard validation per #1085 finding
    #     #2 strengthening.
    #   - reviewer VARCHAR(64) NULL: nullable because 'pending' rows have
    #     no reviewer yet.  Populated when state transitions out of
    #     'pending'.  Format convention: same DECIDED_BY_PREFIXES as
    #     canonical_match_log.decided_by ('human:<username>' for human
    #     reviews; 'service:<svc-name>' for automated review services in
    #     Cohort 5+).  CRUD-boundary length validation enforces 64 cap.
    #   - reviewed_at TIMESTAMPTZ NULL: nullable until state transitions
    #     out of 'pending'.  Partial index supports "recent review
    #     activity" hot path.
    #   - flagged_reason VARCHAR(256) NULL: nullable free-text operator
    #     note explaining why the link was flagged for review.  256 wider
    #     than canonical_match_log.note (TEXT) because this is a
    #     structured short-form reason (not a free-form explanation);
    #     CRUD-boundary length validation enforces the 256 cap (#1085
    #     finding #3 inheritance).
    #   - created_at TIMESTAMPTZ NOT NULL DEFAULT now(): ADR-118 v2.42
    #     sub-amendment A canonical convention.
    #
    # NO updated_at column — reviews use reviewed_at as the state-
    # transition timestamp; created_at + reviewed_at together fully
    # describe the row's lifecycle.  Adding updated_at would mask the
    # transition-vs-creation distinction.
    # =========================================================================
    op.execute(
        """
        CREATE TABLE canonical_match_reviews (
            id              BIGSERIAL    PRIMARY KEY,
            -- review_state vocabulary canonical home:
            -- src/precog/database/constants.py REVIEW_STATE_VALUES.
            -- Adding a value requires lockstep update of both the constant
            -- AND this CHECK constraint (Pattern 73 SSOT discipline).
            link_id         BIGINT       NOT NULL REFERENCES canonical_market_links(id) ON DELETE CASCADE,
            review_state    VARCHAR(16)  NOT NULL,
            -- reviewer free-text format: same DECIDED_BY_PREFIXES convention
            -- as canonical_match_log.decided_by; CRUD-boundary discipline.
            reviewer        VARCHAR(64)  NULL,
            reviewed_at     TIMESTAMPTZ  NULL,
            flagged_reason  VARCHAR(256) NULL,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT ck_canonical_match_reviews_review_state CHECK (review_state IN (
                'pending', 'approved', 'rejected', 'needs_info'
            ))
        )
        """
    )

    # FK-target index on link_id (Samwise discipline).  Hot path:
    # get_reviews_for_link(link_id) — every operator looking at a specific
    # link's review history hits this index.
    op.execute(
        "CREATE INDEX idx_canonical_match_reviews_link_id ON canonical_match_reviews (link_id)"
    )

    # Partial index on review_state='pending' (operator alert hot path).
    # The dominant query is "show me all reviews awaiting operator action";
    # the partial form keeps the index small (most reviews resolve out of
    # 'pending' over time) and matches the WHERE clause exactly.
    op.execute(
        "CREATE INDEX idx_canonical_match_reviews_review_state "
        "ON canonical_match_reviews (review_state) "
        "WHERE review_state = 'pending'"
    )

    # Partial index on reviewed_at IS NOT NULL ("recent review activity"
    # hot path).  DESC ordering supports the dominant ORDER BY direction
    # for the alert query "what reviews has the team resolved this hour /
    # day?".  Excludes pending rows (NULL reviewed_at) — which are covered
    # by the review_state partial index above.
    op.execute(
        "CREATE INDEX idx_canonical_match_reviews_reviewed_at "
        "ON canonical_match_reviews (reviewed_at DESC) "
        "WHERE reviewed_at IS NOT NULL"
    )

    # =========================================================================
    # canonical_match_overrides
    #
    # Column-level rationale (Builder docstring obligation per build spec § 2):
    #   - id BIGSERIAL PK: surrogate.  No child rows FK INTO this table.
    #   - platform_market_id INTEGER NOT NULL REFERENCES markets(id) ON
    #     DELETE CASCADE: override dies with platform market.  Same shape
    #     as canonical_market_links.platform_market_id (slot 0072).
    #   - canonical_market_id BIGINT NULL REFERENCES canonical_markets(id)
    #     ON DELETE RESTRICT: NULLABLE per polarity discriminator
    #     (MUST_NOT_MATCH overrides have no canonical_market_id pointer).
    #     RESTRICT: a canonical_markets row pointed at by a MUST_MATCH
    #     override CANNOT be silently deleted.  Operator must retire the
    #     override first via delete_override().  Symmetric with
    #     canonical_market_links.canonical_market_id ON DELETE RESTRICT
    #     (slot 0072) — both are "human-asserted bindings" requiring
    #     explicit retire.
    #   - polarity VARCHAR(16) NOT NULL CHECK (polarity IN ('MUST_MATCH',
    #     'MUST_NOT_MATCH')): 2-value closed enum.  Pattern 73 SSOT
    #     pointer: canonical home is src/precog/database/constants.py
    #     POLARITY_VALUES (pre-positioned in slot 0072 per S82 council
    #     Section 4 recommendation; slot 0074 finally uses it).
    #   - reason TEXT NOT NULL: free-text operator-readable explanation.
    #     TEXT (no length cap) intentional: operators may include detail
    #     like "this market resolves on a different rule than the
    #     canonical event; they are NOT the same market despite identical
    #     titles."  CRUD-boundary validation rejects empty string + DDL
    #     ck_reason_nonempty CHECK is defense-in-depth.
    #   - created_by VARCHAR(64) NOT NULL: same DECIDED_BY_PREFIXES
    #     convention as canonical_match_log.decided_by.  Always
    #     'human:<username>' for overrides (overrides are human-decided
    #     by definition; the manual_v1-on-human-decided-actions convention
    #     carries through).  CRUD-boundary length validation enforces 64
    #     cap (#1085 finding #3 inheritance).
    #   - created_at TIMESTAMPTZ NOT NULL DEFAULT now(): ADR-118 v2.42
    #     sub-amendment A canonical convention.
    #
    # NO updated_at column — overrides have INSERT-then-DELETE lifecycle;
    # there is no in-place mutation path.  delete_override() removes the
    # row entirely + writes a canonical_match_log audit row.
    #
    # CHECK + UNIQUE constraints:
    #   - uq_canonical_match_overrides_platform_market_id UNIQUE
    #     (platform_market_id): at most ONE override per platform market.
    #     To replace, operator must DELETE the existing override and
    #     INSERT the new one (audit trail goes to canonical_match_log
    #     with action='override' on each operation).
    #   - ck_canonical_match_overrides_polarity: 2-value vocabulary CHECK.
    #   - ck_canonical_match_overrides_polarity_pairing: load-bearing
    #     conditional invariant per ADR-118 v2.41 DDL line 17746-17748.
    #     Three-valued-logic-safe form (IS NULL / IS NOT NULL).  See
    #     migration docstring for the full rationale.
    #   - ck_canonical_match_overrides_reason_nonempty: defense-in-depth
    #     against empty/whitespace-only reason; CRUD-boundary validation
    #     is the primary defense.
    # =========================================================================
    op.execute(
        """
        CREATE TABLE canonical_match_overrides (
            id                   BIGSERIAL    PRIMARY KEY,
            platform_market_id   INTEGER      NOT NULL REFERENCES markets(id)            ON DELETE CASCADE,
            canonical_market_id  BIGINT       NULL     REFERENCES canonical_markets(id)  ON DELETE RESTRICT,
            -- polarity vocabulary canonical home:
            -- src/precog/database/constants.py POLARITY_VALUES.
            -- Pre-positioned in slot 0072; slot 0074 finally uses it.
            polarity             VARCHAR(16)  NOT NULL,
            reason               TEXT         NOT NULL,
            -- created_by free-text format: same DECIDED_BY_PREFIXES convention
            -- as canonical_match_log.decided_by; always 'human:<username>'
            -- for overrides per the human-only invariant (CRUD discipline).
            created_by           VARCHAR(64)  NOT NULL,
            created_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT uq_canonical_match_overrides_platform_market_id
                UNIQUE (platform_market_id),
            CONSTRAINT ck_canonical_match_overrides_polarity CHECK (polarity IN (
                'MUST_MATCH', 'MUST_NOT_MATCH'
            )),
            -- Load-bearing conditional invariant: polarity discriminator
            -- determines NULL/NOT-NULL on canonical_market_id.  See
            -- migration docstring for full rationale + three-valued-logic
            -- safety note (IS NULL / IS NOT NULL, not = NULL / != NULL).
            CONSTRAINT ck_canonical_match_overrides_polarity_pairing CHECK (
                (polarity = 'MUST_NOT_MATCH' AND canonical_market_id IS NULL)
                OR (polarity = 'MUST_MATCH' AND canonical_market_id IS NOT NULL)
            ),
            -- Defense-in-depth: CRUD-boundary rejects empty reason; this
            -- CHECK catches direct-SQL bypass.  length(trim(...)) > 0
            -- rejects both '' and '   ' (whitespace-only).
            CONSTRAINT ck_canonical_match_overrides_reason_nonempty CHECK (
                length(trim(reason)) > 0
            )
        )
        """
    )

    # Partial index on canonical_market_id IS NOT NULL: NULL rows
    # (MUST_NOT_MATCH overrides) don't need indexing on this column;
    # they're looked up via the platform_market_id UNIQUE constraint's
    # underlying index.  Partial form keeps the index small and matches
    # the dominant query "show me overrides pointing at canonical X".
    op.execute(
        "CREATE INDEX idx_canonical_match_overrides_canonical_market_id "
        "ON canonical_match_overrides (canonical_market_id) "
        "WHERE canonical_market_id IS NOT NULL"
    )

    # Polarity index: alert-query hot path "show me all MUST_NOT_MATCH
    # overrides" (operator wants to inspect negative-asserted markets).
    # Non-partial — both polarities are valid query targets.
    op.execute(
        "CREATE INDEX idx_canonical_match_overrides_polarity "
        "ON canonical_match_overrides (polarity)"
    )

    # Recent override activity hot path: ORDER BY created_at DESC dominates
    # operator runbook queries.  DESC index avoids server-side reverse-
    # scan when paired with ORDER BY created_at DESC.
    op.execute(
        "CREATE INDEX idx_canonical_match_overrides_created_at "
        "ON canonical_match_overrides (created_at DESC)"
    )


def downgrade() -> None:
    """Reverse 0074: drop 6 indexes + 2 tables.

    Drop order (object dependencies dictate the sequence):

        1. Indexes — explicit drop for clarity (DROP TABLE would cascade
           them, but explicit DROP keeps the downgrade readable and
           matches Migrations 0072/0073 convention).
        2. ``canonical_match_overrides`` and ``canonical_match_reviews``
           tables — leaf tables.  Drop order between them does not matter
           (no inter-FK between the two tables; they are sibling-shape
           operational-state tables).

    ``IF EXISTS`` used throughout for idempotent rollback per session 59
    ``feedback_idempotent_migration_drops.md``.  Re-running the downgrade
    on a partially-rolled-back DB is a no-op rather than a crash.

    The downgrade is intentionally lossy: any operator review state +
    any override rows are discarded.  This is by design; upgrade-then-
    downgrade-then-upgrade is the supported cycle (round-trip CI gate per
    PR #1081), not downgrade-and-keep-running on a populated production
    DB.  Production-tier rollback that preserves the rows is out of scope;
    if a P0 surfaces post-merge, the cleanest recovery path is a slot
    0076+ reversal migration that explicitly preserves the data (Holden
    Q5 rollback analysis).
    """
    # canonical_match_overrides teardown
    op.execute("DROP INDEX IF EXISTS idx_canonical_match_overrides_created_at")
    op.execute("DROP INDEX IF EXISTS idx_canonical_match_overrides_polarity")
    op.execute("DROP INDEX IF EXISTS idx_canonical_match_overrides_canonical_market_id")
    op.execute("DROP TABLE IF EXISTS canonical_match_overrides")

    # canonical_match_reviews teardown
    op.execute("DROP INDEX IF EXISTS idx_canonical_match_reviews_reviewed_at")
    op.execute("DROP INDEX IF EXISTS idx_canonical_match_reviews_review_state")
    op.execute("DROP INDEX IF EXISTS idx_canonical_match_reviews_link_id")
    op.execute("DROP TABLE IF EXISTS canonical_match_reviews")
