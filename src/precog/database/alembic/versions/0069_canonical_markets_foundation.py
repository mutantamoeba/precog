"""Cohort 2 â€" canonical markets foundation (Phase B.5 ADR-118).

Lands the canonical markets tier â€" the third concrete table of the "Level B"
canonical identity layer from ADR-118 V2.39 (v2.39 amendment, session 73
capture, Cohort 2 amendment).  This migration is the singular DDL artifact of
the Cohort 2 arc; migration 0067 (PR B) shipped ``canonical_event_domains`` +
``canonical_event_types`` + ``canonical_events``; migration 0068 (PR C) shipped
``canonical_entity_kinds`` + ``canonical_entity`` + ``canonical_participant_roles``
+ ``canonical_event_participants``; this migration (0069, PR D) ships
``canonical_markets`` standalone (Cohort 3 / migrations 0070-0073 will land
``canonical_market_links`` + ``canonical_match_log`` + related matching infra).

Scope of 0069 (one table, one index, one BEFORE UPDATE trigger):

    1. ``canonical_markets`` (main) â€" the canonical market row.  Column shape
       is verbatim from ADR-118 V2.39 lines ~17363-17374.  ``canonical_event_id``
       is ``BIGINT NOT NULL REFERENCES canonical_events(id) ON DELETE RESTRICT``
       per ADR-118 V2.39 Cohort 2 amendment decision #5b (markets carry
       settlement; CASCADE would silently delete settlement-bearing rows;
       ``NOT NULL`` precludes ``SET NULL``; the asymmetry with
       ``canonical_event_participants.CASCADE`` is intentional â€"
       participants are denormalization, markets carry settlement +
       observation history).  ``market_type_general`` is an inline
       ``CHECK (... IN ('binary','categorical','scalar'))`` per Cohort 2
       decision #2 â€" closed enum tied to the pmxt #964 NormalizedMarket
       contract; explicitly NOT a Pattern 81 lookup table because the open-set
       test fails (a future market shape requires a code deploy regardless).
       ``natural_key_hash`` is ``BYTEA NOT NULL UNIQUE`` per ADR â€" the
       derivation rule is intentionally APPLICATION-LAYER (deferred to
       Cohort 5 / Migration 0085 seed context), DDL ships agnostic.
       ``retired_at`` is the canonical-tier retirement timestamp (NULL =
       active); per-platform lifecycle lives on platform ``markets.status``,
       canonical-event lifecycle lives on ``canonical_events.lifecycle_phase``
       â€" three distinct concerns kept on three distinct columns per
       Cohort 2 decision #3.  Notably ABSENT: a ``lifecycle_phase`` column
       (intentionally rejected by PM adjudication during session 73 council
       â€" see ADR Cohort 2 amendment rationale decision #3).
    2. FK-column index ``idx_canonical_markets_canonical_event_id`` (full,
       not partial â€" ``canonical_event_id`` is ``NOT NULL``).  ADR-118 V2.39
       documents this index requirement explicitly (lines ~17504-17513) so
       migration scaffold + ADR have a single source of truth.  Same Samwise
       FK-index discipline as Migrations 0067 / 0068.
    3. ``update_canonical_markets_updated_at()`` BEFORE UPDATE trigger
       function + ``trg_canonical_markets_updated_at`` trigger.  Function
       body + trigger DDL verbatim from ADR-118 V2.39 lines ~17381-17392.
       Per Cohort 2 amendment decision #4: this establishes the canonical
       template for the #1007 retrofit (``updated_at`` on ``canonical_events``
       + lookup tables currently has ``DEFAULT now()`` insert-time but no
       maintenance trigger â€" the "misleading tombstone" anti-pattern).  The
       fix per session 73 PM adjudication is to INSTALL the trigger, not
       drop the column.  ``CREATE OR REPLACE FUNCTION`` is used (not the
       ``CREATE CONSTRAINT TRIGGER`` pattern from 0068, which lacks
       ``OR REPLACE``); the trigger itself uses plain ``CREATE TRIGGER``
       and is dropped explicitly in ``downgrade()`` for idempotence.

       **Function-naming convention (Glokta + Ripley convergent finding,
       session 73):** A pre-existing generic function ``update_updated_at_column()``
       already exists in pg_proc with literally identical body, attached to
       ``model_classes`` and ``strategy_types`` triggers. Cohort 2 deliberately
       chooses a per-table function (``update_<table>_updated_at``) for
       grep-ability and to avoid OR-REPLACE aliasing risk if a future cohort
       reuses the same function name with a different body. The #1007 retrofit
       must continue this per-table convention (one function per canonical
       table) OR explicitly migrate the entire canonical tier to the generic
       pattern in a single coordinated PR -- partial reuse breaks Pattern 73
       SSOT. See claude-review on PR #1018 + comment on Issue #1007 for the
       cross-tier reconciliation question.

ADR-amendment rationale decisions (5; see ADR-118 V2.39 lines ~17482-17502 for
the full PM-adjudicated narrative â€" this docstring is the migration-side
pointer per Pattern 73, not a restatement):

    1. DDL audit-column shorthand expanded to full ``TIMESTAMPTZ NOT NULL
       DEFAULT now()`` declarations consistent with Cohort 1 convention.
    2. ``market_type_general`` is an inline CHECK constraint, NOT a Pattern 81
       lookup table.  Closed enum tied to pmxt #964 NormalizedMarket contract.
    3. NO ``lifecycle_phase`` column â€" three-distinct-concerns model.  Per-
       platform lifecycle on platform ``markets.status``; canonical-event
       lifecycle on ``canonical_events.lifecycle_phase``; canonical-market
       retirement on ``retired_at``.
    4. ``updated_at`` + BEFORE UPDATE trigger â€" Cohort 2 establishes the
       template for #1007 retrofit (canonical_events + lookup tables get
       the same trigger pattern in a separate future PR).
    5a. NO Pattern 82 (CONSTRAINT TRIGGER) on ``canonical_markets`` in
        Phase 1 â€" markets are uniform across platforms (binary / categorical /
        scalar shape per pmxt #964); per-platform identity is owned by
        ``canonical_market_links`` (Migration 0071), not by typed back-ref
        columns on ``canonical_markets``.
    5b. ``ON DELETE RESTRICT`` on ``canonical_event_id`` ratified â€"
        settlement-bearing markets must not silently CASCADE-delete; the
        asymmetry with ``canonical_event_participants.CASCADE`` is
        intentional.

Cross-cohort dependencies (carry-forward boundaries â€" out of scope here):

    * ``canonical_market_links`` (Migration 0071, Cohort 3) â€" owns the
      per-platform identity edge from canonical_markets â†' platform markets.
      The CRUD module's ``get_canonical_for_platform_market()`` helper
      (Galadriel Finding 5; Pattern 73 SSOT for "give me canonical for
      this market") is defined at-signature with a ``NotImplementedError``
      stub per ADR-118 V2.39 Cohort 2 amendment Pattern 14 footnote, so
      the contract surface is published before the table that backs it
      ships.
    * ``natural_key_hash`` derivation rule (Cohort 5, Migration 0085) â€"
      this DDL ships the column declaration only.  The rule (hash inputs,
      normalization, tie-breakers) is application-layer
      (``src/precog/matching/``), explicitly NOT DDL.
    * Modifications to platform ``markets`` table (Cohort 10, Migrations
      0086-0089) â€" zero changes here.

Pattern 14 5-step bundle status (per ADR-118 V2.39 Cohort 2 amendment Holden
Finding 11): this PR ships steps 1 + 3 + 4 (Migration + CRUD + unit tests).
Step 2 (SQLAlchemy ORM model) is **N/A** â€" Precog uses raw psycopg2
exclusively, not SQLAlchemy ORM (the CLAUDE.md Tech Stack line is
historically inaccurate; verified by inspection of every existing CRUD module
under ``src/precog/database/crud_*.py``).  Step 5 (integration tests) is
**deferred** to bundle with #1012's Migration 0067 / 0068 integration test
work next session.

Carry-forward from Cohort 1 (0067 / 0068):

    1. Samwise FK-index discipline â€" ADR omits indexes (per ADR convention),
       migrations always add them because planners use them for joins and
       RESTRICT cascade checks.  Full (non-partial) index here because
       ``canonical_event_id`` is ``NOT NULL``; partial WHERE clause would
       not reduce size.
    2. Cohort 1 also skipped Pattern 14 step 3 (no ``crud_canonical_events``
       / ``crud_canonical_entity`` exists yet).  Tracked as a follow-up
       issue for PM â€" out of scope for this PR per scope-boundary
       discipline.

Revision ID: 0069
Revises: 0068
Create Date: 2026-04-24

Issues: #1018 (Cohort 2 ADR-118 V2.39 amendment spec)
Epic: #972 (Canonical Layer Foundation â€" Phase B.5)
ADR: ADR-118 V2.39 (Canonical Identity & Matching; v2.39 Cohort 2 amendment, lines ~17363-17541)
Design review: Holden + Galadriel (session 73), user-adjudicated (session 73; full memo at memory/design_review_cohort2_canonical_markets.md)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0069"
down_revision: str = "0068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create canonical_markets table + FK index + BEFORE UPDATE trigger."""
    # ------------------------------------------------------------------
    # Step 1: Main table â€" canonical_markets
    #
    # Column shape verbatim from ADR-118 V2.39 lines ~17363-17374.
    # BIGSERIAL because the canonical-market tier will eventually aggregate
    # cross-platform market identities and Phase 4+ market counts can
    # exceed 2^31.  ``canonical_event_id`` ON DELETE RESTRICT per Cohort 2
    # amendment decision #5b (markets carry settlement; asymmetry with
    # canonical_event_participants.CASCADE is intentional).
    # ``market_type_general`` is inline CHECK per decision #2 â€" closed enum
    # tied to pmxt #964 NormalizedMarket contract (NOT a Pattern 81 lookup).
    # NO ``lifecycle_phase`` column per decision #3 (three-distinct-concerns
    # model: per-platform lifecycle on platform markets.status; canonical-
    # event lifecycle on canonical_events.lifecycle_phase; canonical-market
    # retirement on retired_at).  ``natural_key_hash`` derivation rule is
    # APPLICATION-LAYER (deferred to Cohort 5).
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE canonical_markets (
            id                    BIGSERIAL    PRIMARY KEY,
            canonical_event_id    BIGINT       NOT NULL REFERENCES canonical_events(id) ON DELETE RESTRICT,
            market_type_general   VARCHAR(32)  NOT NULL CHECK (market_type_general IN ('binary','categorical','scalar')),
            outcome_label         VARCHAR(255),
            natural_key_hash      BYTEA        NOT NULL,
            metadata              JSONB,
            created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            retired_at            TIMESTAMPTZ,
            CONSTRAINT uq_canonical_markets_nk UNIQUE (natural_key_hash)
        )
        """
    )

    # ------------------------------------------------------------------
    # Step 2: FK-column index on canonical_markets.canonical_event_id.
    #
    # Full (non-partial) index â€" canonical_event_id is NOT NULL, so a
    # partial WHERE clause would not reduce size.  Samwise FK-index
    # discipline (ADR omits indexes; migrations always add them).
    # ADR-118 V2.39 lines ~17504-17513 document this index requirement
    # explicitly so migration scaffold + ADR have a single SSOT.
    # ------------------------------------------------------------------
    op.execute(
        "CREATE INDEX idx_canonical_markets_canonical_event_id "
        "ON canonical_markets(canonical_event_id)"
    )

    # ------------------------------------------------------------------
    # Step 3: BEFORE UPDATE trigger function + trigger.
    #
    # Function body + trigger DDL verbatim from ADR-118 V2.39 lines
    # ~17381-17392.  Behavioral spec:
    #
    #   * On INSERT: ``DEFAULT now()`` on the column declaration handles it;
    #     trigger does not fire.
    #   * On UPDATE: trigger sets ``NEW.updated_at = now()`` BEFORE the row
    #     hits storage, so callers cannot accidentally (or maliciously)
    #     write a stale ``updated_at``.
    #
    # ``CREATE OR REPLACE FUNCTION`` is safe for the function (idempotent
    # under re-run); ``CREATE TRIGGER`` (no OR REPLACE form available
    # before PG 14, and we do not assume PG 14+ for the migration) is
    # plain CREATE â€" the downgrade() drops it explicitly with IF EXISTS.
    #
    # Cohort 2 amendment decision #4: this establishes the canonical
    # template for the #1007 retrofit (canonical_events + canonical-tier
    # lookup tables + canonical_event_participants will get the same
    # trigger pattern, with ``<table>`` substitution, in a separate
    # future PR).
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_canonical_markets_updated_at()
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
        CREATE TRIGGER trg_canonical_markets_updated_at
            BEFORE UPDATE ON canonical_markets
            FOR EACH ROW
            EXECUTE FUNCTION update_canonical_markets_updated_at()
        """
    )


def downgrade() -> None:
    """Reverse 0069: drop trigger + function + index + table.

    Drop order (object dependencies dictate the sequence):

        1. ``trg_canonical_markets_updated_at`` â€" depends on the function
           AND the table.  Drops first so the function and table can be
           dropped cleanly.
        2. ``update_canonical_markets_updated_at()`` â€" depends on nothing
           after the trigger is gone.  Drops next.
        3. ``idx_canonical_markets_canonical_event_id`` â€" explicit drop
           for clarity (DROP TABLE would cascade it, but explicit DROP
           keeps the downgrade readable and matches Cohort 1 convention).
        4. ``canonical_markets`` â€" leaf table.  Drops last.

    ``IF EXISTS`` used throughout for idempotent rollback â€" rerunning
    the downgrade on a partially-rolled-back DB is a no-op rather than
    a crash.
    """
    op.execute("DROP TRIGGER IF EXISTS trg_canonical_markets_updated_at ON canonical_markets")
    op.execute("DROP FUNCTION IF EXISTS update_canonical_markets_updated_at()")
    op.execute("DROP INDEX IF EXISTS idx_canonical_markets_canonical_event_id")
    op.execute("DROP TABLE IF EXISTS canonical_markets")
