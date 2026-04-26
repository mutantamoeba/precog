"""Cohort 3 first slot — ``match_algorithm`` lookup table foundation.

The first concrete artifact of the Cohort 3 matching infrastructure (ADR-118
v2.40 lines 17621-17628; v2.41 amendment Cohort 3 slot count adjudication —
session 78 user adjudication of the 5-slot framing).  This migration is the
standalone parent lookup that 0072+ FK into; isolating it in its own slot is
the Pattern 14 hygiene call from the session 78 design council
(``memory/design_review_cohort_3_synthesis.md`` L29-L31; council convergence at
synthesis E1 user-adjudicated to 5 slots).

Scope (one table, one seeded row):

    1. ``match_algorithm`` (lookup) — 1 seed row at Phase 1: ``manual_v1`` /
       ``1.0.0``.  Open enum encoded as a lookup table (Pattern 81); new
       algorithms (e.g., ``keyword_jaccard_v1``, ``ml_v3``) land via INSERT
       seeds in their cohort-of-origin migrations, not ALTER TABLE.

Pattern 81 (lookup convention) — canonical instance:
    ``match_algorithm`` is the precursor that justifies Pattern 81's existence
    (ADR-118 line ~17475 cites it as the precursor).  The full algorithm name
    set is open: ``keyword_jaccard_v1`` ships with Phase 3 (when the title-based
    matcher lands), ML algorithms (``ml_v3``) ship Phase 5+.  We do NOT add a
    CHECK on ``name`` — that would defeat the lookup-table justification.

Pattern 73 (SSOT for code_ref) — with reservation note:
    ``code_ref = 'precog.matching.manual_v1'`` is the canonical SSOT pointer
    that Cohort 5+ resolver code uses to locate the matcher implementation.
    The path **does not yet exist** in the repo as of this migration — this
    is the Phase 1 schema-only seed and the resolver work is a Cohort 5
    deliverable (Migration 0085 territory).  The path is reserved by Cohort
    3 seeding and implemented when Cohort 5 resolver work lands; if a future
    PR creates the module with a signature that diverges from what
    ``match_algorithm.code_ref`` consumers expect, the SSOT pointer breaks
    silently.  Mitigation: the integration test at
    ``tests/integration/database/test_migration_0071_match_algorithm.py``
    pins the seeded ``code_ref`` value (Pattern 22 / pre-existing test
    discipline + Holden Risk A from build_spec_0071_holden_memo.md).

Pattern 84 (NOT VALID + VALIDATE) — N/A carve-out:
    Fresh empty table; CHECK constraints on populated tables don't apply
    (the table doesn't exist before this migration).  Per Pattern 84 § "When
    NOT to Apply" both criteria met:

        * Zero rows in dev/staging at migration time (table doesn't exist).
        * No expected rows by production deploy time beyond the single
          ``manual_v1`` seed inserted in this same migration.

    ``match_algorithm`` has zero CHECK constraints anyway (the only constraint
    is the composite UNIQUE on ``(name, version)``), so Pattern 84 is doubly
    N/A.  Same shape as Migration 0070's ``lifecycle_phase`` CHECK carve-out
    against pre-populated ``canonical_events`` (which had zero rows).

Critical Pattern #6 (Immutable Versioning) — load-bearing:
    No ``updated_at`` column.  Re-tuning a matcher = INSERT a new row with a
    new version (e.g., ``manual_v1`` / ``1.1.0``); the prior row stays
    immutable.  INSERT-only discipline post-seed.  Algorithms enter via
    migration seeds, not runtime CRUD; Cohort 5+ resolver code may add a
    ``create_match_algorithm`` helper when registering new algorithms, but
    no UPDATE / DELETE path exists by design.  Documented here so a future
    PR proposing "add updated_at" argues against ADR text rather than against
    a one-line code comment.

Idempotent seed (Pattern 67 ``ON CONFLICT`` discipline, mirrors Migration 0067
``_insert_domain_seeds`` / ``_insert_event_type_seeds``):
    The ``INSERT ... ON CONFLICT (name, version) DO NOTHING`` clause makes
    re-running this migration on a partially-applied DB a no-op rather than a
    crash.  ``ON CONFLICT`` is non-negotiable: partial-migration replay must
    succeed.

Cohort 3 5-slot adjudication (session 78 user adjudication; ADR-118 v2.41
amendment):
    Cohort 3 was originally framed as 4 migrations (0071-0074) at v2.40 time,
    with ``match_algorithm`` bundled into the link-tables slot.  The session
    78 design council surfaced a Pattern 14 hygiene divergence: Galadriel +
    Elrond preserved the v2.40 slot table; Holden split ``match_algorithm``
    to its own slot on the grounds that one DDL artifact per migration
    matches Pattern 14 better.  User adjudicated 5 slots (synthesis E1).
    Post-adjudication slot mapping:

        * 0071 → ``match_algorithm`` (this migration)
        * 0072 → ``canonical_market_links`` + ``canonical_event_links``
        * 0073 → ``canonical_match_log``
        * 0074 → ``canonical_match_reviews`` + ``canonical_match_overrides``
        * 0075 → ``observation_source`` registry

    Contract-displacement consequence: ``crud_canonical_markets.py`` shipped
    with ~10 docstring/exception-message references to "Migration 0071 =
    canonical_market_links"; this PR bumps those to "Migration 0072" so the
    CRUD module's published-contract surface stays in sync with the
    post-adjudication slot mapping.

Revision ID: 0071
Revises: 0070
Create Date: 2026-04-26

Issues: Epic #972 (Canonical Layer Foundation — Phase B.5), #1058 (P41
    design-stage codification — first Cohort 3 builder dispatch under
    Tier 0 + S82)
ADR: ADR-118 v2.40 lines 17621-17628 (canonical DDL anchor); v2.41 amendment
    (Cohort 3 slot count adjudication, session 78)
Design council: session 78 (Galadriel + Holden + Elrond); user-adjudicated
    via synthesis E1; build spec at
    ``memory/build_spec_0071_holden_memo.md``
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0071"
down_revision: str = "0070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# =========================================================================
# Seed data (pinned in the migration — ADR-118 v2.40 line 17628 + Phase 1
# commitments line ~17929).
#
# Pattern 73 discipline: this list is the SINGLE source of truth in code.
# The ADR body names the same value; future seed-only migrations extend by
# INSERT, never by duplication here.  ``id`` is allocated by BIGSERIAL in
# insertion order; downstream JOINs resolve via the business key
# ``(name, version)``, never a hardcoded integer.
# =========================================================================

# Phase 1 seed — exactly one row per ADR-118 v2.40 line 17628 + Phase 1
# commitments line ~17929 ("Phase 1 seeds exactly one row: ('manual_v1',
# '1.0.0')").  ``code_ref`` is the Pattern 73 SSOT pointer reserved for
# Cohort 5 resolver work (Migration 0085 territory); the path does not
# yet exist in the repo and is implemented when Cohort 5 lands.
_MATCH_ALGORITHM_SEED: list[tuple[str, str, str, str]] = [
    # (name, version, code_ref, description)
    (
        "manual_v1",
        "1.0.0",
        "precog.matching.manual_v1",
        "Phase 1 baseline: every link decided manually; confidence = 1.0 for human-decided rows.",
    ),
]


def _insert_match_algorithm_seed(conn: sa.engine.Connection) -> None:
    """Insert the Phase 1 seed row.

    Uses ``ON CONFLICT (name, version) DO NOTHING`` for idempotence: rerunning
    the migration on a partially-migrated DB is a no-op rather than a crash.
    Mirrors the helper shape used in Migration 0067 (``_insert_domain_seeds``,
    ``_insert_event_type_seeds``).
    """
    for name, version, code_ref, description in _MATCH_ALGORITHM_SEED:
        conn.execute(
            sa.text(
                "INSERT INTO match_algorithm (name, version, code_ref, description) "
                "VALUES (:name, :version, :code_ref, :description) "
                "ON CONFLICT (name, version) DO NOTHING"
            ),
            {
                "name": name,
                "version": version,
                "code_ref": code_ref,
                "description": description,
            },
        )


def upgrade() -> None:
    """Create ``match_algorithm`` lookup table + seed Phase 1 ``manual_v1`` row."""
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # Step 1: Lookup table — match_algorithm
    #
    # Column-level rationale:
    #   - id BIGSERIAL PK: children (canonical_market_links / canonical_event_
    #     links / canonical_match_log) FK INTO this table; BIGSERIAL future-
    #     proofs against algorithm-version proliferation in Phase 5+.
    #   - name VARCHAR(64): operator-readable algorithm family name.  Seed
    #     value 'manual_v1'.  Width 64 matches ADR.
    #   - version VARCHAR(16): semver-shaped.  Seed value '1.0.0'.  Re-tuning
    #     a matcher = new row with new version (Critical Pattern #6
    #     immutability).
    #   - code_ref VARCHAR(255) NOT NULL: Pattern 73 SSOT pointer.  NOT NULL
    #     per synthesis L30 binding (every algorithm row reserves a real
    #     module path even when the module ships in a later cohort).  Width
    #     255 buys margin for long Phase 5+ ML algorithm code-refs (e.g.,
    #     'precog.matching.experimental.ml_v3_with_features_2026Q1' ~ 64
    #     chars; 255 leaves headroom without semver-shaped column overhead).
    #   - description TEXT NULL: operator commentary.  Nullable.
    #   - created_at TIMESTAMPTZ NOT NULL DEFAULT now(): Cohort 1+2 audit-
    #     column convention.
    #   - retired_at TIMESTAMPTZ NULL: NULL = active.  Mirrors
    #     canonical_markets retirement pattern.  No updated_at — algorithms
    #     are immutable per Critical Pattern #6.
    #   - CONSTRAINT uq_match_algorithm UNIQUE (name, version): verbatim per
    #     ADR-118 v2.40 line 17626.  Composite uniqueness lets
    #     ('manual_v1','1.0.0') and ('manual_v1','1.1.0') coexist while
    #     ('manual_v1','1.0.0') cannot duplicate.  Doubles as an index.
    #
    # Indexes: PK and the composite UNIQUE provide everything needed.  No
    # FK-target indexes (this table is a parent only — children FK INTO it).
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE match_algorithm (
            id           BIGSERIAL    PRIMARY KEY,
            name         VARCHAR(64)  NOT NULL,
            version      VARCHAR(16)  NOT NULL,
            code_ref     VARCHAR(255) NOT NULL,
            description  TEXT         NULL,
            created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
            retired_at   TIMESTAMPTZ  NULL,
            CONSTRAINT uq_match_algorithm UNIQUE (name, version)
        )
        """
    )

    # ------------------------------------------------------------------
    # Step 2: Seed Phase 1 manual_v1 row.
    # ------------------------------------------------------------------
    _insert_match_algorithm_seed(conn)


def downgrade() -> None:
    """Reverse 0071: drop the match_algorithm table.

    IF EXISTS for idempotent rollback (per session 59
    ``feedback_idempotent_migration_drops.md``).  Seed rows drop with the
    table — no separate DELETE needed.  The downgrade is intentionally
    lossy: any 0072+ migration that FKs match_algorithm.id will fail to
    apply on a downgraded DB until 0071 is re-applied (this is by design;
    upgrade-then-downgrade-then-upgrade is the supported cycle, not
    downgrade-and-keep-running).
    """
    op.execute("DROP TABLE IF EXISTS match_algorithm")
