"""Canonical Python source-of-truth constants for the database tier.

Pattern 73 SSOT (CLAUDE.md Critical Pattern #8): any value list appearing
in more than one location MUST have ONE canonical definition + pointers
from the others.  This module is that canonical location for cross-cutting
database vocabulary that future state-machine code, projection views, and
migrations will need to share with DDL constraints.

When to add a constant here:
    - The value(s) are referenced by DDL (CHECK, lookup table, trigger
      function)
    - AND will be referenced by Python code (state-machine transitions,
      projection writers, CRUD functions, validators)
    - AND drift between the two locations would corrupt data or surface
      as silent failures

When NOT to add a constant here:
    - Value is referenced only inside one migration (Pattern 6 — migrations
      are immutable post-ship; no consumer to share with)
    - Value is referenced only in tests (test code defines its own
      fixtures)
"""

from __future__ import annotations

from typing import Final

CANONICAL_EVENT_LIFECYCLE_PHASES: Final[tuple[str, ...]] = (
    "proposed",
    "listed",
    "pre_event",
    "live",
    "suspended",
    "settling",
    "resolved",
    "voided",
)
"""Canonical 8-value vocabulary for ``canonical_events.lifecycle_phase``.

Authoritative per ADR-118 V2.40 Cohort 1 carry-forward item 3.

Migration 0070 (CHECK on ``canonical_events.lifecycle_phase``) and
Migration 0077 (CHECK on ``canonical_event_phase_log.phase``, when it
lands) both enforce this list at the DDL layer.  State-machine transition
code, projection views, and the phase-log consumer MUST import from here
rather than hardcoding string literals (Pattern 73 SSOT).

The tuple ordering reflects the canonical state-machine progression:
``proposed -> listed -> pre_event -> live -> (suspended -> live |
settling -> resolved | voided)``.  Ordering MAY be relied on by consumers
(e.g., phase-precedence comparisons); a future migration that reorders
values MUST update this constant in the same change.

See DEVELOPMENT_PATTERNS V1.38 Pattern 84 for the two-phase
NOT VALID + VALIDATE pattern that any future migration adding similar
vocabulary CHECKs should follow.
"""


LINK_STATE_VALUES: Final[tuple[str, ...]] = (
    "active",
    "retired",
    "quarantined",
)
"""Canonical 3-value vocabulary for ``canonical_market_links.link_state`` and
``canonical_event_links.link_state``.

Authoritative per ADR-118 v2.41 amendment + Cohort 3 design council L5.

Migration 0072 enforces this list at the DDL layer via inline CHECK
constraints on both link tables.  Adding a new state requires lockstep
update of both this constant AND a migration ALTERing the CHECK
constraint on both tables — drift between Python and DDL would produce
silent state-machine bugs (an algorithm-side write of an unknown state
would be rejected by DDL but pass Python validation, or vice versa).

State-machine semantics (S82 council Section 4):
    ``active``       — current canonical-to-platform binding; the
                       EXCLUDE-USING-btree partial index admits at most
                       one ``active`` row per platform-row id.
    ``retired``      — operator-decided reversal of an earlier ``active``;
                       coexists freely with other retired/quarantined rows.
    ``quarantined``  — algorithm-flagged uncertainty pending review;
                       coexists freely; surfaces in operator alert queries.

Per CLAUDE.md Critical Pattern #8 (Pattern 73 SSOT): CRUD modules, state-
machine code, projection writers, and tests MUST import from this constant
rather than hardcoding the string list.

Pattern 81 carve-out: this is intentionally NOT a lookup table.  The state
set is closed (every value binds to code branches per Pattern 81 §
"When NOT to Apply").  See ``Migration 0072`` docstring for the full
carve-out rationale.
"""


REVIEW_STATE_VALUES: Final[tuple[str, ...]] = (
    "pending",
    "approved",
    "rejected",
    "needs_info",
)
"""Canonical 4-value vocabulary for ``canonical_match_reviews.review_state``.

Authoritative per ADR-118 v2.41 amendment + Cohort 3 design council L14 +
session-80 S82 council Section 4 (review state machine) +
session-82 slot-0074 build spec § 3.

Migration 0074 enforces this list at the DDL layer via an inline CHECK
constraint on ``canonical_match_reviews.review_state``.  Adding a new state
requires lockstep update of both this constant AND a migration ALTERing
the CHECK constraint — drift between Python and DDL would produce silent
state-machine bugs.

State-machine semantics (S82 council Section 4):
    ``pending``     — review row created; no operator action yet.
                      Surfaces in the operator alert query (``WHERE
                      review_state = 'pending'``); partial index supports it.
    ``approved``    — operator has reviewed and confirmed the link is
                      correct.  Triggers a canonical_match_log row with
                      action='review_approve'.
    ``rejected``    — operator has reviewed and confirmed the link is
                      INCORRECT.  Triggers a canonical_match_log row with
                      action='review_reject'.  Rejected reviews typically
                      pair with a subsequent operator-driven retire_link()
                      on the underlying canonical_market_links row, but
                      the schema does not enforce the pairing.
    ``needs_info``  — operator has reviewed but cannot decide; flags the
                      link for further investigation (e.g., requires data
                      from another source).  Treated like 'pending' by the
                      alert query but with reviewer + reviewed_at populated
                      to record that someone has looked.

Per CLAUDE.md Critical Pattern #8 (Pattern 73 SSOT): the
``crud_canonical_match_reviews`` CRUD module uses this constant in
*real-guard* validation (not side-effect-only import) per #1085 finding
#2 inheritance from slot 0073 — ``if review_state not in REVIEW_STATE_VALUES:
raise ValueError(...)``.

Pattern 81 carve-out: this is intentionally NOT a lookup table.  The
state set is closed (every value binds to code branches per Pattern 81 §
"When NOT to Apply"); same carve-out rationale as ``LINK_STATE_VALUES`` /
``ACTION_VALUES``.  See ``Migration 0074`` docstring for the full
Pattern 81 non-application explanation.
"""


POLARITY_VALUES: Final[tuple[str, ...]] = (
    "MUST_MATCH",
    "MUST_NOT_MATCH",
)
"""Canonical 2-value vocabulary for ``canonical_match_overrides.polarity``.

Pre-positioned in slot 0072 per S82 council Section 4 recommendation; slot
0074 finally USES it in real-guard validation inside the
``crud_canonical_match_overrides`` module (per #1085 finding #2
strengthening).  Migration 0074 enforces this list at the DDL layer via an
inline CHECK constraint on ``canonical_match_overrides.polarity``.

Authoritative per ADR-118 v2.41 amendment + Cohort 3 design council L34 +
session-82 slot-0074 build spec § 3.

Semantics:
    ``MUST_MATCH``      — operator-asserted positive override; the matcher
                          MUST emit an active link for this (canonical,
                          platform) pair regardless of algorithm score.
                          Pairs with NON-NULL ``canonical_market_id`` per
                          ``ck_canonical_match_overrides_polarity_pairing``.
    ``MUST_NOT_MATCH``  — operator-asserted negative override; the matcher
                          MUST NOT emit an active link for this pair, even
                          if algorithm score crosses the threshold.  Pairs
                          with NULL ``canonical_market_id`` per the same
                          pairing CHECK.

Per CLAUDE.md Critical Pattern #8 (Pattern 73 SSOT): the
``crud_canonical_match_overrides`` CRUD module uses this constant in
*real-guard* validation per the slot-0074 #1085 finding #2 strengthening
discipline — ``if polarity not in POLARITY_VALUES: raise ValueError(...)``.

Pattern 81 carve-out: this is intentionally NOT a lookup table.  The
polarity set is closed (every value binds to code branches per Pattern 81
§ "When NOT to Apply"); same carve-out rationale as ``LINK_STATE_VALUES``
/ ``ACTION_VALUES`` / ``REVIEW_STATE_VALUES``.  See ``Migration 0074``
docstring for the full Pattern 81 non-application explanation.
"""


ACTION_VALUES: Final[tuple[str, ...]] = (
    "link",  # initial active link created
    "unlink",  # active link transitioned to retired
    "relink",  # retired link re-activated (ABA path)
    "quarantine",  # active link transitioned to quarantined
    "override",  # human override row created (in canonical_match_overrides)
    "review_approve",  # canonical_match_reviews row transitioned to 'approved'
    "review_reject",  # canonical_match_reviews row transitioned to 'rejected'
)
"""Canonical 7-value vocabulary for ``canonical_match_log.action``.

Authoritative per ADR-118 v2.41 amendment + Cohort 3 design council L11 +
session-80 PM adjudication of Open Item B (Uhura logging-frame argument:
UNIFIED SHAPE > NORMALIZED SHAPE for the audit ledger — the log carries
review/override actions alongside link-state-transition actions so an
operator querying "everything that touched this platform_market" gets a
single chronological stream).

Migration 0073 enforces this list at the DDL layer via an inline CHECK
constraint on ``canonical_match_log.action``.  Adding a new action requires
lockstep update of both this constant AND a migration ALTERing the CHECK
constraint — drift between Python and DDL would produce silent audit-
ledger bugs (a CRUD-side write of an unknown action would be rejected by
DDL but pass Python validation, or vice versa).

Action semantics (S82 council Section 4 + slot 0073 build spec § 2):
    ``link``           — initial ``active`` link inserted into
                         canonical_market_links.  Pairs 1:1 with the link
                         table INSERT in the slot-0073 two-table-write.
    ``unlink``         — existing ``active`` link transitioned to
                         ``retired`` via ``crud_canonical_market_links.
                         retire_link()``.
    ``relink``         — previously ``retired`` link re-activated (the ABA
                         path: A → retire → B → retire → A again).  The
                         re-activation is a fresh ``active`` row, but the
                         log row's ``prior_link_id`` points to the
                         predecessor for audit traceability.
    ``quarantine``     — ``active`` link transitioned to ``quarantined``
                         (algorithm-flagged uncertainty pending review).
    ``override``       — human override row created in
                         ``canonical_match_overrides`` (slot 0074 territory).
                         Logged here for unified audit-stream visibility;
                         the log row carries the override's polarity in
                         ``features`` JSONB, not in a discriminator column.
    ``review_approve`` — ``canonical_match_reviews`` row transitioned to
                         ``approved`` (slot 0074 territory).
    ``review_reject``  — ``canonical_match_reviews`` row transitioned to
                         ``rejected`` (slot 0074 territory).

Per CLAUDE.md Critical Pattern #8 (Pattern 73 SSOT): the
``crud_canonical_match_log.append_match_log_row()`` CRUD function uses
this constant in *real-guard* validation (not side-effect-only import) —
``if action not in ACTION_VALUES: raise ValueError(...)``.  This is the
#1085-finding-#2 strengthening of the slot-0072 ``LINK_STATE_VALUES``
side-effect-only convention: real-guard usage turns a documentation
cite into an executable contract.

Pattern 81 carve-out: this is intentionally NOT a lookup table.  The
action set is closed (every value binds to code branches per Pattern 81 §
"When NOT to Apply"); same carve-out rationale as ``LINK_STATE_VALUES``.
See ``Migration 0073`` docstring for the full Pattern 81 non-application
explanation.
"""


DECIDED_BY_PREFIXES: Final[tuple[str, ...]] = (
    "human:",
    "service:",
    "system:",
)
"""Canonical 3-prefix vocabulary for ``decided_by`` columns on
``canonical_match_log`` + ``canonical_market_links`` + ``canonical_event_links``.

Authoritative per ADR-118 v2.41 amendment + Cohort 3 design council L24 +
session-80 Uhura S82 Builder consideration #5 (decided_by Pattern 73 SSOT
pointer).

The ``decided_by`` column is ``VARCHAR(64) NOT NULL`` on all three tables;
a DDL CHECK cannot enforce free-text format (string-format validation is
Pattern 81 non-application territory and overkill for a free-text actor
field), so the discipline lives at THIS constant + the convention in
``crud_canonical_match_log.py``'s module docstring + the real-guard
validation in ``append_match_log_row()``.

Conventions (canonical):
    ``'human:<username>'``    — human-driven action.  Examples:
                                ``'human:eric'``, ``'human:etollef@pm.me'``.
                                Override rows always use this prefix
                                (overrides are by definition human-decided).
    ``'service:<svc-name>'``  — autonomous matcher service.  Examples:
                                ``'service:matching-v1'``,
                                ``'service:keyword_jaccard_v1'``.  The
                                Cohort 5+ matcher writes service prefixes.
    ``'system:<context>'``    — seed/migration/system writes.  Examples:
                                ``'system:migration_0073'``, ``'system:test'``.
                                Used for fixture rows + bulk backfills.

Per CLAUDE.md Critical Pattern #8 (Pattern 73 SSOT): the
``crud_canonical_match_log.append_match_log_row()`` CRUD function uses
this constant in real-guard validation —
``if not any(decided_by.startswith(p) for p in DECIDED_BY_PREFIXES): raise``.
Length-bound enforcement (``len(decided_by) <= 64``) is also at the CRUD
boundary per #1085 finding #3 (the ``retire_reason`` length-not-validated
case the slot-0072 review surfaced; slot 0073 inherits the lesson).

Pattern 81 non-application: the prefix set is closed (3 actor categories
covering every conceivable origin of a match decision); a lookup table is
not warranted — see ``Migration 0073`` docstring for the explicit carve-
out rationale.
"""


PHASE_1_SOURCE_KEYS: Final[tuple[str, ...]] = ("espn", "kalshi", "manual")
"""Phase 1 baseline source_key values for ``observation_source``.

Authoritative per ADR-118 v2.40 lines 17785-17791 + line 18006 (canonical
seed list) + slot 0075 build spec § 4 (Phase 1 baseline = ``espn``,
``kalshi``, ``manual``).

Migration 0075 seeds these three rows into the ``observation_source``
lookup table.  Future sources (``noaa``, ``bls``, ``fivethirtyeight``,
etc.) extend the lookup table via INSERT seeds in their cohort-of-origin
migrations (Phase 3+ data-source-expansion territory).

**Documentation-not-enforcement framing (Pattern 81 lookup-not-CHECK):**
Unlike ``LINK_STATE_VALUES`` / ``ACTION_VALUES`` which back DDL CHECK
constraints with closed-enum semantics, ``observation_source.source_key``
has NO CHECK constraint by design — it is an OPEN ENUM encoded as a
lookup table per Pattern 81.  This Python tuple documents the Phase 1
baseline at code level (so test code + CRUD code can reference the
canonical Phase 1 set as Pattern 73 SSOT real-guard) but is NOT a closed
enforcement set.  CRUD code (when it ships in Cohort 5+) will likely
treat ``source_key`` as opaque text and not validate against this tuple.

Per CLAUDE.md Critical Pattern #8 (Pattern 73 SSOT): test code uses this
constant in real-guard validation against the seeded rows (the
``test_observation_source_phase_1_seeds_present`` integration test asserts
all three keys round-trip through the lookup table).

Pattern 81 lookup convention: future sources extend by INSERT seeds in
their cohort-of-origin migrations, never by ALTER TABLE.  Same shape as
``match_algorithm`` slot 0071 — ``match_algorithm`` is the precursor
that justifies Pattern 81's existence, and ``observation_source`` is its
sibling lookup-table peer.
"""


OBSERVATION_KIND_VALUES: Final[tuple[str, ...]] = (
    "game_state",  # Sports observations (Cohort 4 — only kind exercised this cohort)
    "weather",  # Weather observations (Cohort 9 — deferred under Option D)
    "poll",  # Poll-release observations (Cohort 6+)
    "econ",  # Econ-print observations (Cohort 6+)
    "news",  # News-event observations (Cohort 7+)
    "market_snapshot",  # Cross-platform market-state observations (Cohort 5+)
)
"""Canonical 6-value vocabulary for ``canonical_observations.observation_kind``.

Authoritative per ADR-118 V2.43 Cohort 4 + slot 0078 build spec § 3 +
session 85 4-agent design council convergence.

Migration 0078 enforces this list at the DDL layer via an inline CHECK
constraint on ``canonical_observations.observation_kind``.  Adding a new
kind requires lockstep update of both this constant AND a migration
ALTERing the CHECK constraint — drift between Python and DDL would
produce silent ingest-pipeline bugs.

Per CLAUDE.md Critical Pattern #8 (Pattern 73 SSOT): the
``crud_canonical_observations.append_observation_row()`` CRUD function
uses this constant in real-guard validation —
``if observation_kind not in OBSERVATION_KIND_VALUES: raise ValueError(...)``.
This is the same #1085-finding-#2 strengthening Cohort 3 slot 0073
established (real-guard usage, not side-effect-only ``# noqa: F401``).

Cohort 4 ONLY exercises ``'game_state'``; the other kinds are reserved
forward-pointers to later cohorts (Cohorts 5-9).  The DDL CHECK is sized
for the eventual full-vocabulary set so future-cohort migrations don't
need to ALTER the CHECK every time a new kind is added — they only seed
new rows + update this Python constant.

Pattern 81 carve-out: this is intentionally NOT a lookup table.  The
kind set is closed (every value binds to per-kind projection code in
later cohorts per Pattern 81 § "When NOT to Apply"); same carve-out
rationale as ``LINK_STATE_VALUES`` / ``ACTION_VALUES`` /
``REVIEW_STATE_VALUES`` / ``POLARITY_VALUES``.  See ``Migration 0078``
docstring for the full Pattern 81 non-application explanation.
"""


PARTITION_STRATEGY_VALUES: Final[tuple[str, ...]] = (
    "range_monthly_ingested_at",  # Cohort 4 canonical_observations strategy
    # Future strategies (e.g., "range_quarterly", "list_kind") are reserved
    # here when added.
)
"""Documentation-only vocabulary for partitioning strategies.

Authoritative per ADR-118 V2.43 Cohort 4 + slot 0078 build spec § 3.

This tuple is **documentation-only** — there is NO DDL CHECK constraint
backing it (PostgreSQL partition strategy is encoded in the
``PARTITION BY`` clause itself, not a free-form column).  The constant
exists so future cohorts adding new partitioning shapes have a canonical
home to extend, and so anyone reading the Cohort 4 schema can answer
"what partitioning strategies does this codebase commit to?" by reading
ONE Python tuple rather than walking every migration file.

Pattern 73 SSOT: when a future cohort adds a new strategy (e.g.,
``range_quarterly`` for a finer-grained partition shape, or
``list_kind`` for a kind-based partition scheme), the strategy name is
added here AND cited in the new migration's docstring.  Drift between
"strategy named in migration X's PARTITION BY clause" and "strategy
listed in this tuple" would surface as a silent docs-vs-DDL gap.

Per Cohort 4 council convergence + V2.43 Item 2: ``range_monthly_ingested_at``
is the strategy committed to for ``canonical_observations`` based on
Holden D1 PM call (``ingested_at`` is the partition key) + the operational
cadence of monthly partition addition (~7 days before expiration per the
Cohort 4 operator runbook).
"""


RECONCILIATION_OUTCOME_VALUES: Final[tuple[str, ...]] = (
    "match",  # Source observation matches projection
    "drift",  # Source vs projection differ within tolerance
    "mismatch",  # Source vs projection differ beyond tolerance (alert-worthy)
    "missing_dim",  # Projection has row but no canonical_observation parent
    "missing_fact",  # canonical_observation has no projection in expected per-kind table
    "ambiguous",  # Multiple projections for one canonical_observation
)
"""Canonical 6-value vocabulary for the future Cohort 5+ reconciler.

Authoritative per ADR-118 V2.43 Cohort 4 + slot 0078 build spec § 3 +
session 85 4-agent design council Cohort 4 reconciler design.

**Defined in Cohort 4, consumed in Cohort 5+** — slot 0078 ships this
constant alongside ``canonical_observations`` so the canonical reconciler
module (when it materializes in Cohort 5+) inherits a stable vocabulary
rather than re-deriving it post-hoc.  The ``canonical_observations_
reconciliation_anomaly_count`` metric (Cohort 4 native metric #2 per
build spec § 7) increments per row per non-``match`` outcome, riding the
``system_health.details`` JSONB surface until a typed
``canonical_reconciliation_results`` table lands (Cohort 5+, V2.43
Item 4).

Outcome semantics (build spec § 7 + Cohort 4 council convergence):

    ``match``         — Source observation row equals the projection
                        within strict equality (per per-kind comparator).
    ``drift``         — Source vs projection differ but within
                        per-kind drift tolerance; soft signal, not alert-
                        worthy by itself but trended over time.
    ``mismatch``      — Source vs projection differ beyond drift
                        tolerance; alert-worthy.  Reconciler logs the
                        diff fingerprint to ``system_health.details``
                        JSONB.
    ``missing_dim``   — Per-kind projection has a row but no parent
                        ``canonical_observations`` row exists.  Indicates
                        the writer skipped the parent INSERT (audit gap).
    ``missing_fact``  — ``canonical_observations`` row has no per-kind
                        projection in the expected table.  Indicates a
                        consumer is behind or not yet onboarded.
    ``ambiguous``     — Multiple projection rows exist for one
                        ``canonical_observations`` row.  Indicates the
                        per-kind table's UNIQUE invariant is missing or
                        an upstream writer double-wrote.

Per CLAUDE.md Critical Pattern #8 (Pattern 73 SSOT): when the Cohort 5+
reconciler module ships, it imports this constant and uses it in the
outcome-tally code path.  Schema-level enforcement is deferred until
the typed ``canonical_reconciliation_results`` table lands (Cohort 5+);
until then the JSONB ``details`` payload uses these strings.

Pattern 81 carve-out: this vocabulary is **closed** (every outcome
binds to operator-runbook-investigation branches per Pattern 81 §
"When NOT to Apply"); not a lookup table.  Same shape as
``LINK_STATE_VALUES`` / ``ACTION_VALUES`` / ``REVIEW_STATE_VALUES`` /
``POLARITY_VALUES`` / ``OBSERVATION_KIND_VALUES``.
"""


SOURCE_KIND_VALUES: Final[tuple[str, ...]] = (
    "api",
    "scrape",
    "manual",
    "derived",
)
"""Phase 1 baseline source_kind values for ``observation_source``.

Authoritative per ADR-118 v2.40 lines 17785-17791 (DDL example values) +
slot 0075 build spec § 3.

The four values document the Phase 1 ingestion-mechanism vocabulary:

    ``api``      — pulled via authenticated API (e.g., ``espn``, ``kalshi``).
    ``scrape``   — pulled via HTML scraping or undocumented endpoint.
    ``manual``   — human-entered observation (e.g., ``manual`` source).
    ``derived``  — synthesized from other observations (e.g., a rolling
                   average over an upstream API source).

**Documentation-not-enforcement framing (Pattern 81 lookup-not-CHECK):**
Unlike ``LINK_STATE_VALUES`` / ``ACTION_VALUES`` which back DDL CHECK
constraints with closed-enum semantics, ``observation_source.source_kind``
has NO CHECK constraint by design — it is an OPEN ENUM encoded as a
lookup table per Pattern 81.  Future kinds (e.g., ``streaming``,
``webhook``) extend this column via new seed values in cohort-of-origin
migrations, never by ALTER TABLE.  This Python tuple is the documented
anchor at code level, NOT a closed enforcement set.

Per CLAUDE.md Critical Pattern #8 (Pattern 73 SSOT): when CRUD code
ships in Cohort 5+, the canonical observation pipeline can reference
this constant as the documented Phase 1 baseline; runtime validation
against the lookup table itself (``SELECT source_kind FROM
observation_source WHERE source_key = ?``) is the authoritative source.

Pattern 81 lookup convention: same shape as ``match_algorithm`` slot
0071 — ``observation_source`` is the lookup-table sibling for ingestion
sources; future kinds extend by INSERT seeds, never by CHECK ALTER.
"""
