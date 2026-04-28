"""Cohort 3 fifth slot — ``observation_source`` lookup table foundation.

The fifth concrete artifact of the Cohort 3 matching infrastructure
(ADR-118 v2.40 lines 17785-17791 + line 18006 canonical seed list; v2.41
amendment Cohort 3 5-slot adjudication — session 78 user adjudication).
This migration is the standalone observation-pipeline parent lookup that
slot 0076+ (``canonical_observations`` partitioned fact table +
``canonical_event_phase_log``) FK into; isolating it in its own slot
matches the Pattern 14 hygiene call from the session 78 design council
(``memory/design_review_cohort_3_synthesis.md`` L37-L38; council
convergence at synthesis E1 user-adjudicated to 5 slots).

Scope (one table, three seeded rows):

    1. ``observation_source`` (lookup) — 3 seed rows at Phase 1: ``espn``,
       ``kalshi``, ``manual``.  Open enums for ``source_key`` and
       ``source_kind`` encoded as a lookup table (Pattern 81); new
       sources (e.g., ``noaa``, ``bls``, ``fivethirtyeight``) land via
       INSERT seeds in their cohort-of-origin migrations, not ALTER TABLE.

Pattern 81 (lookup convention) — sibling of ``match_algorithm``:
    ``observation_source`` is the second canonical lookup-table instance
    in Cohort 3, sibling to ``match_algorithm`` (slot 0071 — the precursor
    that justifies Pattern 81's existence per ADR-118 line ~17489).  The
    full ``source_key`` set is open: ``noaa`` / ``bls`` /
    ``fivethirtyeight`` ship with Phase 3+ data-source-expansion work
    (per ``project_data_source_expansion.md``).  We do NOT add CHECK
    constraints on ``source_key`` or ``source_kind`` — that would defeat
    the lookup-table justification and force every new source through a
    schema migration rather than a seed insert.

Pattern 73 (SSOT pointer for source value-sets):
    The ``source_key`` and ``source_kind`` value-set conventions are
    codified in ``src/precog/database/constants.py`` as
    ``PHASE_1_SOURCE_KEYS = ('espn', 'kalshi', 'manual')`` and
    ``SOURCE_KIND_VALUES = ('api', 'scrape', 'manual', 'derived')``.
    Those constants are **documentation-not-enforcement** (per Pattern 81
    open-enum semantics) — the canonical authoritative store is the
    ``observation_source`` table itself.  Test code references the
    constants as Phase 1 baseline anchors; CRUD code (when it ships in
    Cohort 5+) will treat ``source_key`` as opaque text.

Pattern 84 (NOT VALID + VALIDATE) — N/A carve-out (DOUBLY):
    Fresh empty table; CHECK constraints on populated tables don't apply
    (the table doesn't exist before this migration).  Per Pattern 84 §
    "When NOT to Apply" both criteria met:

        * Zero rows in dev/staging at migration time (table doesn't exist).
        * No expected rows by production deploy time beyond the three
          Phase 1 seeds inserted in this same migration.

    ``observation_source`` has zero CHECK constraints anyway (open enums
    on ``source_key`` + ``source_kind`` per Pattern 81 carve-out), so
    Pattern 84 is doubly N/A.  Same shape as Migration 0071's
    ``match_algorithm`` carve-out (which also has zero CHECKs by Pattern
    81 design).

Critical Pattern #6 (Immutable Versioning) — load-bearing:
    No ``updated_at`` column.  Re-categorizing a source = INSERT a new
    row + retire the old (set ``retired_at = now()``); the prior row stays
    immutable.  INSERT-only / SET-retired-at-only discipline post-seed.
    Sources enter via migration seeds; runtime CRUD (when it ships in
    Cohort 5+) may add a ``register_source`` helper but no UPDATE / DELETE
    path exists by design.  Documented here so a future PR proposing
    "add updated_at" argues against ADR text rather than against a
    one-line code comment.

Critical Pattern #1 (Decimal precision) — N/A:
    No Decimal-typed columns in this lookup table.  Logged here for
    completeness so the Pattern checklist is fully addressed.

Pattern 67 (idempotent seed via ``ON CONFLICT``) — load-bearing:
    The ``INSERT ... ON CONFLICT (source_key) DO NOTHING`` clause makes
    re-running this migration on a partially-applied DB a no-op rather
    than a crash.  ``ON CONFLICT`` is non-negotiable: partial-migration
    replay must succeed.  Mirrors Migration 0071's ``match_algorithm``
    seed helper (with ``(name, version)`` swapped for the single-column
    ``source_key`` business key).

Cohort 3 5-slot adjudication (session 78 user adjudication; ADR-118 v2.41
amendment):
    Cohort 3 was originally framed as 4 migrations (0071-0074) at v2.40
    time, with ``observation_source`` bundled or deferred.  The session 78
    design council surfaced a Pattern 14 hygiene divergence; user
    adjudicated 5 slots (synthesis E1).  Post-adjudication slot mapping:

        * 0071 → ``match_algorithm``
        * 0072 → ``canonical_market_links`` + ``canonical_event_links``
        * 0073 → ``canonical_match_log``
        * 0074 → ``canonical_match_overrides`` + ``canonical_match_reviews``
        * 0075 → ``observation_source`` registry (this migration)

    Slot ordering note (build spec § 9): slot 0075 ships ahead of slot
    0074 because the two are independent (no FK dependencies between
    ``observation_source`` and the matching ledger).  Alembic's linear
    chain just needs sequential revision numbers, not topological-by-
    design ordering.  Slot 0075 closes a small backlog item; slot 0074
    deserves a fresh dispatch with full attention.

UNIQUE-key choice (build spec § 2 + ADR-118 line 17791):
    Single-column ``UNIQUE (source_key)`` rather than the composite
    ``(name, version)`` shape used by ``match_algorithm``.  There is no
    version concept for sources: ``ESPN-as-of-2026`` IS the same source
    as ``ESPN-as-of-2030`` (the API may change but the source identity
    doesn't).  If a source ever fundamentally re-emerges with different
    semantics, the migration path is to retire the old row (set
    ``retired_at = now()``) and INSERT a new ``source_key`` (e.g.,
    ``espn_v2``), not to version the existing row.

FK-target preparedness (build spec § 2 closing note):
    ``observation_source`` is the parent.  ``canonical_observations``
    (slot 0076+) and ``canonical_event_phase_log`` (slot 0076+) will FK
    INTO ``observation_source.id``.  The PK + the ``UNIQUE (source_key)``
    constraint together provide everything those FKs need.

Revision ID: 0075
Revises: 0073
Create Date: 2026-04-27

NOTE on Alembic chain ordering (build spec § 9 deviation, PM-callout
flagged):
    The slot 0075 build spec § 9 says "slot 0075 ships ahead of slot
    0074".  Since slot 0074 does NOT yet exist in the alembic versions
    directory at the time slot 0075 ships, this migration's
    ``down_revision`` chains to 0073 (the current head).  When slot 0074
    ships in a future session, its ``down_revision`` will be 0075 (the
    linear-chain consequence).  This preserves Alembic's
    topological-by-revision-number invariant; slot 0074 retains its
    revision number 0074 even though it ships chronologically AFTER
    slot 0075 — Alembic only requires the chain to be linear, not
    monotonic-by-number.

Issues: Epic #972 (Canonical Layer Foundation — Phase B.5), #1058 (P41
    design-stage codification — Cohort 3 builder dispatch under
    Tier 0 + S82)
ADR: ADR-118 v2.40 lines 17785-17791 (canonical DDL anchor) + line 18006
    (canonical seed list); v2.41 amendment (Cohort 3 5-slot adjudication,
    session 78)
Design council: session 78 (Galadriel + Holden + Elrond); user-adjudicated
    via synthesis E1; build spec at
    ``memory/build_spec_0075_pm_memo.md``
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0075"
down_revision: str = "0073"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# =========================================================================
# Seed data (pinned in the migration — ADR-118 line 18006 + slot 0075
# build spec § 4).
#
# Pattern 73 discipline: this list is the SINGLE source of truth in code
# for the Phase 1 baseline.  The ADR body names the same value list;
# future seed-only migrations (Phase 3+ data-source-expansion territory)
# extend by INSERT, never by duplication here.  ``id`` is allocated by
# BIGSERIAL in insertion order; downstream JOINs resolve via the business
# key ``source_key``, never a hardcoded integer.
#
# ``authoritative_for`` is left None at Phase 1 — the canonical
# observation-kind vocabulary lands in slot 0076+ when
# ``canonical_observations`` ships.  ESPN is the conceptual
# ``sport_game_state`` authority and Kalshi is the conceptual
# ``market_snapshot`` authority, but Phase 1 holds the JSONB array null
# until the kind vocabulary exists.
# =========================================================================

# Phase 1 seed — exactly three rows per ADR-118 line 18006 ("Seeds:
# match_algorithm(manual_v1), observation_source(espn, kalshi, manual)").
_OBSERVATION_SOURCE_SEED: list[tuple[str, str, str | None]] = [
    # (source_key, source_kind, authoritative_for)
    ("espn", "api", None),
    ("kalshi", "api", None),
    ("manual", "manual", None),
]


def _insert_observation_source_seed(conn: sa.engine.Connection) -> None:
    """Insert the Phase 1 seed rows.

    Uses ``ON CONFLICT (source_key) DO NOTHING`` for idempotence: rerunning
    the migration on a partially-migrated DB is a no-op rather than a
    crash.  Mirrors the helper shape used in Migration 0071
    (``_insert_match_algorithm_seed``) and Migration 0067
    (``_insert_domain_seeds`` / ``_insert_event_type_seeds``).

    The single-column ``ON CONFLICT (source_key)`` matches the single-
    column ``UNIQUE (source_key)`` constraint defined in the upgrade DDL.
    """
    for source_key, source_kind, authoritative_for in _OBSERVATION_SOURCE_SEED:
        conn.execute(
            sa.text(
                "INSERT INTO observation_source (source_key, source_kind, authoritative_for) "
                "VALUES (:source_key, :source_kind, :authoritative_for) "
                "ON CONFLICT (source_key) DO NOTHING"
            ),
            {
                "source_key": source_key,
                "source_kind": source_kind,
                "authoritative_for": authoritative_for,
            },
        )


def upgrade() -> None:
    """Create ``observation_source`` lookup table + seed Phase 1 three rows."""
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # Step 1: Lookup table — observation_source
    #
    # Column-level rationale:
    #   - id BIGSERIAL PK: children (canonical_observations,
    #     canonical_event_phase_log — slot 0076+) FK INTO this table;
    #     BIGSERIAL future-proofs against source proliferation in Phase
    #     3+ data-source-expansion (per project_data_source_expansion.md).
    #   - source_key VARCHAR(64) NOT NULL: operator-readable source
    #     identifier (e.g., 'espn', 'kalshi', 'manual', 'noaa', 'bls',
    #     'fivethirtyeight').  Unique business key.  Width 64 matches
    #     match_algorithm.name + canonical_markets external_id width
    #     precedent.  No CHECK constraint per Pattern 81 — open enum
    #     extends by INSERT seed.
    #   - source_kind VARCHAR(32) NOT NULL: ingestion mechanism (e.g.,
    #     'api', 'scrape', 'manual', 'derived').  Open enum — future
    #     kinds (e.g., 'streaming', 'webhook') extend this column via
    #     new seed values, NOT ALTER TABLE.  No CHECK constraint per
    #     Pattern 81.
    #   - authoritative_for JSONB NULL: array of
    #     canonical_observations.observation_kind values this source is
    #     authoritative for (e.g., ['sport_game_state'] for ESPN,
    #     ['market_snapshot'] for Kalshi).  Phase 1 seeds set
    #     authoritative_for to NULL; canonical observation kinds land in
    #     slot 0076+ when canonical_observations ships.
    #   - created_at TIMESTAMPTZ NOT NULL DEFAULT now(): v2.42 sub-
    #     amendment A audit-column convention; same shape as
    #     match_algorithm slot 0071 + canonical_market_links slot 0072.
    #   - retired_at TIMESTAMPTZ NULL: NULL = active.  Mirrors
    #     match_algorithm retirement pattern.  No updated_at — sources
    #     are immutable per Critical Pattern #6 (re-categorize a source
    #     by inserting a new row + retiring the old).
    #   - CONSTRAINT uq_observation_source_key UNIQUE (source_key):
    #     verbatim per ADR-118 v2.40 line 17791.  Single-column UNIQUE:
    #     source_key alone is the business identity (different from
    #     match_algorithm's composite (name, version) — there is no
    #     version concept for sources).  Doubles as an index for FK
    #     resolution by source_key.
    #
    # Indexes: PK and the UNIQUE (source_key) provide everything needed.
    # No FK-target indexes (this table is a parent only — children FK
    # INTO it from slot 0076+).
    #
    # CHECK constraints: ZERO.  Pattern 81 carve-out — source_key and
    # source_kind are open enums encoded as lookup-table rows (the
    # ``observation_source`` table itself is the canonical store);
    # adding a CHECK would defeat Pattern 81 by forcing schema
    # migrations for every new source.  See test_migration_0075_
    # observation_source.py::test_observation_source_no_check_
    # constraints for the load-bearing pin.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE observation_source (
            id                 BIGSERIAL    PRIMARY KEY,
            source_key         VARCHAR(64)  NOT NULL,
            source_kind        VARCHAR(32)  NOT NULL,
            authoritative_for  JSONB        NULL,
            created_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
            retired_at         TIMESTAMPTZ  NULL,
            CONSTRAINT uq_observation_source_key UNIQUE (source_key)
        )
        """
    )

    # ------------------------------------------------------------------
    # Step 2: Seed Phase 1 baseline rows (espn, kalshi, manual).
    # ------------------------------------------------------------------
    _insert_observation_source_seed(conn)


def downgrade() -> None:
    """Reverse 0075: drop the observation_source table.

    IF EXISTS for idempotent rollback (per session 59
    ``feedback_idempotent_migration_drops.md``).  Seed rows drop with the
    table — no separate DELETE needed.  The downgrade is intentionally
    lossy: any 0076+ migration that FKs ``observation_source.id`` will
    fail to apply on a downgraded DB until 0075 is re-applied (this is
    by design; upgrade-then-downgrade-then-upgrade is the supported
    cycle, not downgrade-and-keep-running).
    """
    op.execute("DROP TABLE IF EXISTS observation_source")
