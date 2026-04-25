"""Cohort 1 carry-forward hardening — items 1 + 3 from #1011 council adjudication.

Adds two additive integrity fences to the Cohort 1 canonical foundation tables.
Both are pure DDL (no data backfill), additive (no existing constraint
modification), and verified-clean against live state at migration authoring time.

    1. Partial unique index ``uq_canonical_participant_roles_role_when_cross_domain``
       on ``canonical_participant_roles (role) WHERE domain_id IS NULL`` —
       enforces the "exactly one cross-domain role per role text" invariant
       that ADR-118 V2.38 decision #4 framed as "this role is shared across
       domains."  The existing composite ``uq_canonical_participant_roles_domain_role``
       UNIQUE handles domain-scoped uniqueness; PostgreSQL treats NULL as
       distinct in unique constraints, so cross-domain rows ``(NULL, 'yes_side')``
       could silently duplicate without this partial index.  Closes the
       Pattern 81 §"Nullable Parent Scope" gap (V1.37 lines ~12042-12056).
       Live state at authoring: 10 domain-scoped seed rows, 0 NULL-domain
       rows — index commits clean with no backfill.

    2. CHECK constraint ``canonical_events_lifecycle_phase_check`` on
       ``canonical_events.lifecycle_phase`` restricting values to the 8
       canonical state-machine phases per ADR-118 V2.39 (line ~17644 inline
       enumeration): 'proposed', 'listed', 'pre_event', 'live', 'suspended',
       'settling', 'resolved', 'voided'.  Closed enum tied to code branches
       (state-machine transition logic, projection views, future
       canonical_event_phase_log consumer) — Pattern 81 §"When NOT to Apply
       (Keep CHECK)" criteria are met (V1.37 lines ~12067-12072).  Live state
       at authoring: 0 canonical_events rows in dev — CHECK commits clean
       with no backfill.

       **Forward-pointer (load-bearing per ADR-118 v2.40):** when Migration
       0077 lands ``canonical_event_phase_log``, that migration MUST add an
       identical CHECK on the ``phase`` column with the same 8 values.
       Vocabulary drift between ``canonical_events.lifecycle_phase`` (the dim)
       and ``canonical_event_phase_log.phase`` (the audit log) would bypass
       the audit-as-correctness-check by the same bug — a typo in a
       phase-transition writer would corrupt both surfaces simultaneously.
       Two-fence enforcement is the design intent.

Council: #1011 (Holden + Galadriel + Joe Chip session 74).  Items 2
(``sequence_number`` DEFAULT — KEEP no-default), 4 (Pattern 82 forward-only
direction policy + load-bearing regression test), and 5 (Pattern 83
seed NULL guard) are NOT in this migration's scope — they are
documentation-only (ADR-118 v2.40 in PR 1 of bundle; DEVELOPMENT_PATTERNS
V1.37 in PR #1030) or applied to FUTURE migrations only (Pattern 83's
"no retrofit on shipped migrations" append-only principle).

Future-cohort consideration (audit finding, session 75; ADR-118 v2.40
footnote): ``canonical_events.(game_id, series_id)`` is itself a Pattern 82
instance not yet enforced — discriminator is ``event_type_id``; rule is
"single-game event types → game_id NOT NULL; series event types →
series_id NOT NULL."  To be enforced at Cohort 6 seeder (Migration 0085
territory, when canonical_events gets seeded 1:1 from games + series).
Out of scope here.

Cohort numbering note: ADR-118 v2.39 originally reserved migrations 0070-0073
for Cohort 3 (matching infrastructure).  Cohort 3 has not started; Cohort 1
carry-forward (#1011) was filed first.  Claiming slot 0070 here; Cohort 3's
4 migrations slot at 0071-0074 (or wherever they land — the migration
sequence is just a number; what matters is the dependency graph).
``plan_schema_hardening_arc.md`` to be updated at session-end.

References:
  - ADR-118 V2.40 Cohort 1 Carry-Forward Amendment (PR 1 of 3-PR bundle)
  - DEVELOPMENT_PATTERNS V1.37 §Pattern 81, §Pattern 82 V2, §Pattern 83 (PR #1030)
  - memory/design_review_1011_holden_memo.md (schema-safety frame)
  - memory/design_review_1011_galadriel_memo.md (cross-module harmony frame)
  - memory/design_review_1011_joechip_memo.md (assumption-decay frame)

Revision ID: 0070
Revises: 0069
Create Date: 2026-04-25

Issues: #1011 (carry-forward bundle)
Epic: #972 (Canonical Layer Foundation — Phase B.5)
ADR: ADR-118 V2.40 (Cohort 1 Carry-Forward Amendment — Items 1 + 3)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0070"
down_revision: str = "0069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add partial unique index + lifecycle_phase CHECK constraint."""
    # ------------------------------------------------------------------
    # Item 1: Partial unique index — cross-domain role singleton.
    #
    # The existing composite UNIQUE (domain_id, role) handles domain-scoped
    # rows. NULL domain_id rows ("shared across domains" per ADR-118 V2.38
    # decision #4) need an additional partial UNIQUE on (role) to enforce
    # "exactly one cross-domain row per role text" — PG treats NULL as
    # distinct in composite UNIQUE.
    #
    # IF NOT EXISTS for idempotent re-run on partially-applied state.
    # ------------------------------------------------------------------
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "uq_canonical_participant_roles_role_when_cross_domain "
        "ON canonical_participant_roles (role) "
        "WHERE domain_id IS NULL"
    )

    # ------------------------------------------------------------------
    # Item 3: CHECK constraint on canonical_events.lifecycle_phase.
    #
    # 8-value closed state-machine vocabulary per ADR-118 V2.39 line ~17644
    # inline enumeration. Pattern 81 §"When NOT to Apply (Keep CHECK)"
    # criteria are met: values tied to code branches in state-machine
    # transition logic, projection views, and the future
    # canonical_event_phase_log consumer.
    #
    # Forward-pointer (load-bearing per ADR-118 v2.40): Migration 0077
    # canonical_event_phase_log MUST add an identical CHECK on phase column.
    #
    # Idempotency: DROP-IF-EXISTS first, then ADD. Re-running the migration
    # is safe on partially-applied state.
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE canonical_events "
        "DROP CONSTRAINT IF EXISTS canonical_events_lifecycle_phase_check"
    )
    op.execute(
        "ALTER TABLE canonical_events "
        "ADD CONSTRAINT canonical_events_lifecycle_phase_check "
        "CHECK (lifecycle_phase IN ("
        "'proposed','listed','pre_event','live',"
        "'suspended','settling','resolved','voided'))"
    )


def downgrade() -> None:
    """Drop CHECK and partial unique index in reverse order."""
    op.execute(
        "ALTER TABLE canonical_events "
        "DROP CONSTRAINT IF EXISTS canonical_events_lifecycle_phase_check"
    )
    op.execute("DROP INDEX IF EXISTS uq_canonical_participant_roles_role_when_cross_domain")
