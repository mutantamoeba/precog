"""Cohort 1B — canonical entity foundation (Phase B.5 ADR-118).

Lands the canonical entity tier — the second concrete implementation of the
"Level B" canonical identity layer from ADR-118 V2.38 (v2.38 amendment, session
72 capture, issue #996).  This migration is PR C of the Cohort 1 arc; migration
0067 (PR B) already shipped ``canonical_event_domains`` + ``canonical_event_types``
+ ``canonical_events``.

Scope of 0068 (four tables, two seeded lookups, one CONSTRAINT TRIGGER):

    1. ``canonical_entity_kinds`` (lookup) — 12 seed rows: team, fighter,
       candidate, storm, company, location, person, product, country,
       organization, commodity, media.  Open-enum encoded as a lookup table
       instead of a CHECK constraint — new entity kinds land as INSERT rows,
       not ALTER TABLE (Pattern 81 candidate; ADR-118 V2.38 decision #1).
    2. ``canonical_entity`` (main polymorphic) — the canonical entity row.
       Column shape is verbatim from ADR-118 V2.38 lines ~17360-17369; FK into
       ``canonical_entity_kinds`` replaces the pre-v2.38 CHECK constraint on
       string ``entity_kind``.  ``ref_team_id`` is a NULLABLE typed back-ref
       into the platform-sports ``teams`` dimension — populated when
       ``entity_kind = 'team'``, NULL otherwise (per ADR-118 V2.38 decision
       #5).  Polymorphic-back-ref integrity ("team-kind rows MUST carry
       ref_team_id") is enforced via a CONSTRAINT TRIGGER (see #3 below) —
       not an inline CHECK, because PG CHECK cannot subquery the lookup
       table to resolve ``entity_kind_id`` to text.
    3. CONSTRAINT TRIGGER + function — ``enforce_canonical_entity_team_backref``.
       Function body verbatim from ADR-118 V2.38 lines ~17376-17392.  Trigger
       is ``DEFERRABLE INITIALLY IMMEDIATE`` so bulk INSERTs can stage rows
       before the constraint fires at statement end.  This is the canonical
       Pattern 82 candidate (CONSTRAINT TRIGGER for polymorphic typed
       back-ref) — first concrete implementation; future ``ref_fighter_id``,
       ``ref_candidate_id``, ``ref_storm_id`` columns each get their own
       trigger off the same template.
    4. ``canonical_participant_roles`` (lookup with NULLABLE ``domain_id``) —
       10 seed rows scoped to specific domains (sports.home/away,
       fighting.fighter_a/b, politics.candidate/moderator,
       weather.affected_location, entertainment.nominee/winner/host).  Per
       ADR-118 V2.38 decision #4 the ``domain_id`` column is NULLABLE so
       cross-domain roles (future ``yes_side`` etc.) fit the same table.
       Composite UNIQUE ``(domain_id, role)``; PG treats NULL ``domain_id``
       rows as distinct (mirrors the ``UNIQUE`` semantics callers expect for
       cross-domain rows).
    5. ``canonical_event_participants`` (main typed relation) — the
       per-event participant row.  Column shape is verbatim from ADR-118
       V2.38 lines ~17401-17408.  FK into ``canonical_events`` is ON DELETE
       CASCADE (the event going away takes its participant rows with it);
       FKs into ``canonical_entity`` and ``canonical_participant_roles`` are
       ON DELETE RESTRICT (entities and roles outlive any single event).
       ``sequence_number`` is NOT NULL with NO default — forces callers to
       reason about sequence explicitly (per Glokta carry-forward from 0067
       review; the 10-candidate election case is the motivating example, see
       ADR-118 V2.38 decision #6).  Composite UNIQUE
       ``(canonical_event_id, role_id, sequence_number)`` replaces the
       pre-v2.38 ``UNIQUE (canonical_event_id, role)``.

FK-column indexes (Samwise discipline — ADR omits these; migrations always add
them because planners use them for joins and RESTRICT cascade checks):

    * ``idx_canonical_entity_entity_kind_id`` — full (entity_kind_id NOT NULL)
    * ``idx_canonical_entity_ref_team_id`` — partial WHERE ``ref_team_id IS
      NOT NULL`` (typical for nullable FK; non-team-kind rows have NULL)
    * ``idx_canonical_participant_roles_domain_id`` — partial WHERE
      ``domain_id IS NOT NULL`` (cross-domain rows have NULL ``domain_id``;
      Glokta carry-forward #2 from 0067 review)
    * ``idx_canonical_event_participants_canonical_event_id`` — full
    * ``idx_canonical_event_participants_entity_id`` — full
    * ``idx_canonical_event_participants_role_id`` — full

Pattern 73 discipline: seed values are taken verbatim from ADR-118 V2.38 lines
~17423-17424.  No paraphrase, no drift.  The CONSTRAINT TRIGGER function body
is also verbatim from ADR-118 V2.38 lines ~17376-17398 — if the ADR is
amended, this migration is the one place the trigger DDL lives in code.

Carry-forward from Glokta adversarial review of 0067:

    1. CONSTRAINT TRIGGER has NO ``OR REPLACE`` form — downgrade DROPs the
       trigger, then DROPs the function (both ``IF EXISTS`` for idempotence).
    2. Partial index on nullable FK columns (``ref_team_id``, ``domain_id``).
    3. ``teams.team_id`` is single-column PK (verified MCP), FK works direct.
    4. Seed ordering: ``canonical_entity_kinds`` seeded BEFORE
       ``canonical_entity`` is INSERT-able (function trigger does
       seed-order-agnostic lookup via ``WHERE id = NEW.entity_kind_id``).
    5. ``sequence_number`` has no default — forces caller awareness.
    6. ``canonical_event_id`` is ON DELETE CASCADE (different from RESTRICT
       on the other FKs in this migration; matches ADR-118 V2.38 line
       ~17403).
    7. ``ON DELETE`` design question for ``canonical_events.game_id`` /
       ``series_id`` is filed as #1004; non-blocking for 0068.

Revision ID: 0068
Revises: 0067
Create Date: 2026-04-23

Issues: #996 (Cohort 1 ADR-118 amendment spec)
Epic: #972 (Canonical Layer Foundation — Phase B.5)
ADR: ADR-118 V2.38 (Canonical Identity & Matching; v2.38 amendment)
Design review: Holden + Galadriel (session 71), user-adjudicated (session 71)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0068"
down_revision: str = "0067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# =========================================================================
# Seed data (pinned in the migration — ADR-118 V2.38 lines ~17423-17424).
#
# Pattern 73 discipline: these lists are the SINGLE source of truth in code.
# The ADR body names the same values; future seed-only migrations extend by
# INSERT, never by duplication here.  ``id`` is allocated by SERIAL in
# insertion order; downstream JOINs resolve via the business key
# (``entity_kind`` / ``role`` text), never a hardcoded integer.
# =========================================================================

# 12 entity kinds, per ADR-118 V2.38 decision #1.  Ordering matches ADR prose
# (team first as the Phase 1 sports-platform anchor; new kinds appended).
_ENTITY_KIND_SEED: list[tuple[str, str]] = [
    ("team", "Sports team (Phase 1 anchor — typed back-ref via ref_team_id)"),
    ("fighter", "Combat-sport athlete (MMA, boxing)"),
    ("candidate", "Political candidate / nominee"),
    ("storm", "Named weather system (hurricane, typhoon)"),
    ("company", "Publicly-traded or named corporate entity"),
    ("location", "Geographic location (city, region, venue)"),
    ("person", "Individual person (non-political, non-fighter)"),
    ("product", "Product / launch / SKU"),
    ("country", "Sovereign nation / nation-state"),
    ("organization", "Non-corporate organization (NGO, league, institution)"),
    ("commodity", "Tradable commodity (oil, wheat, gold)"),
    ("media", "Media property (film, show, album)"),
]

# 10 participant roles, per ADR-118 V2.38 decision #4.  All seed rows have
# concrete ``domain_id`` (no cross-domain rows in the initial seed); future
# cross-domain roles (e.g. ``yes_side``) land via INSERT with NULL
# ``domain_id``.  Tuple shape: (domain_key, role, description).
_PARTICIPANT_ROLE_SEED: list[tuple[str, str, str]] = [
    ("sports", "home", "Home-side sports participant"),
    ("sports", "away", "Away-side sports participant"),
    ("fighting", "fighter_a", "First fighter in a combat-sport bout"),
    ("fighting", "fighter_b", "Second fighter in a combat-sport bout"),
    ("politics", "candidate", "Political candidate / contestant in an election"),
    ("politics", "moderator", "Debate moderator / non-contestant"),
    ("weather", "affected_location", "Location affected by the weather event"),
    ("entertainment", "nominee", "Award nominee"),
    ("entertainment", "winner", "Award winner (resolved outcome)"),
    ("entertainment", "host", "Event host / presenter"),
]


def _insert_entity_kind_seeds(conn: sa.engine.Connection) -> None:
    """Insert the 12 base entity-kind rows.

    Uses ``ON CONFLICT (entity_kind) DO NOTHING`` for idempotence: rerunning
    the migration on a partially-migrated DB is a no-op rather than a crash.
    """
    for entity_kind, description in _ENTITY_KIND_SEED:
        conn.execute(
            sa.text(
                "INSERT INTO canonical_entity_kinds (entity_kind, description) "
                "VALUES (:entity_kind, :description) "
                "ON CONFLICT (entity_kind) DO NOTHING"
            ),
            {"entity_kind": entity_kind, "description": description},
        )


def _insert_participant_role_seeds(conn: sa.engine.Connection) -> None:
    """Insert the per-domain participant-role rows.

    ``domain_id`` resolved via subquery on ``domain`` text — avoids hardcoded
    integer ids that would drift across fresh vs incremental runs and pairs
    with the cross-cohort dependency on 0067 having already seeded
    ``canonical_event_domains``.  Uses
    ``ON CONFLICT (domain_id, role) DO NOTHING`` for idempotence.
    """
    for domain_key, role, description in _PARTICIPANT_ROLE_SEED:
        conn.execute(
            sa.text(
                "INSERT INTO canonical_participant_roles (domain_id, role, description) "
                "VALUES ("
                "    (SELECT id FROM canonical_event_domains WHERE domain = :domain_key),"
                "    :role,"
                "    :description"
                ") "
                "ON CONFLICT (domain_id, role) DO NOTHING"
            ),
            {
                "domain_key": domain_key,
                "role": role,
                "description": description,
            },
        )


def upgrade() -> None:
    """Create the four canonical-entity tables + CONSTRAINT TRIGGER, seed lookups, add FK indexes."""
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # Step 1: Lookup table — canonical_entity_kinds
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE canonical_entity_kinds (
            id           SERIAL PRIMARY KEY,
            entity_kind  TEXT NOT NULL UNIQUE,
            description  TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    # Seed entity kinds BEFORE creating canonical_entity — the trigger
    # function does a runtime lookup via ``WHERE id = NEW.entity_kind_id`` so
    # the seed must be in place before any INSERT into canonical_entity.
    _insert_entity_kind_seeds(conn)

    # ------------------------------------------------------------------
    # Step 2: Main polymorphic table — canonical_entity
    #
    # Column shape verbatim from ADR-118 V2.38 lines ~17360-17369.  BIGSERIAL
    # because the canonical-entity tier will eventually aggregate cross-
    # platform identities (teams, fighters, candidates, storms, …) and
    # Phase 4+ entity counts can grow large.  ``ref_team_id`` is the typed
    # back-ref into the platform-sports ``teams`` dimension (NULLABLE — only
    # populated when ``entity_kind = 'team'``).  Integrity rule
    # ("team-kind rows MUST carry ref_team_id") is enforced via the
    # CONSTRAINT TRIGGER created in Step 3 below — NOT an inline CHECK,
    # because PG CHECK cannot subquery the lookup table.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE canonical_entity (
            id              BIGSERIAL PRIMARY KEY,
            entity_kind_id  INTEGER NOT NULL REFERENCES canonical_entity_kinds(id) ON DELETE RESTRICT,
            entity_key      TEXT NOT NULL,
            display_name    TEXT NOT NULL,
            ref_team_id     INTEGER REFERENCES teams(team_id) ON DELETE RESTRICT,
            metadata        JSONB,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            -- Polymorphic back-ref integrity enforced via CONSTRAINT TRIGGER (created after this table)
            CONSTRAINT uq_canonical_entity_kind_key UNIQUE (entity_kind_id, entity_key)
        )
        """
    )

    # ------------------------------------------------------------------
    # Step 3: Polymorphic back-ref enforcement (Pattern 82 candidate).
    #
    # Function body + trigger DDL verbatim from ADR-118 V2.38 lines
    # ~17376-17398.  Behavioral spec:
    #
    #   * When entity_kind='team', ref_team_id MUST be NOT NULL
    #     → trigger raises EXCEPTION otherwise.
    #   * When entity_kind != 'team', ref_team_id can be anything (NULL is
    #     typical, but a future design could overload it).
    #
    # ``DEFERRABLE INITIALLY IMMEDIATE`` so bulk INSERTs stage rows before
    # the constraint fires at statement end.  Lookup is dynamic (resolves
    # ``entity_kind_id`` → text via canonical_entity_kinds) so the trigger
    # is seed-order agnostic — no hardcoded integer literals that would
    # break across fresh vs incremental runs.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_canonical_entity_team_backref()
        RETURNS TRIGGER AS $$
        DECLARE
            v_entity_kind TEXT;
        BEGIN
            SELECT entity_kind INTO v_entity_kind
              FROM canonical_entity_kinds
             WHERE id = NEW.entity_kind_id;

            IF v_entity_kind = 'team' AND NEW.ref_team_id IS NULL THEN
                RAISE EXCEPTION
                  'canonical_entity: entity_kind=team requires ref_team_id NOT NULL (canonical_entity.id=%)',
                  NEW.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_canonical_entity_team_backref
            AFTER INSERT OR UPDATE OF entity_kind_id, ref_team_id ON canonical_entity
            DEFERRABLE INITIALLY IMMEDIATE
            FOR EACH ROW
            EXECUTE FUNCTION enforce_canonical_entity_team_backref()
        """
    )

    # FK-column indexes on canonical_entity.
    op.execute(
        "CREATE INDEX idx_canonical_entity_entity_kind_id ON canonical_entity(entity_kind_id)"
    )
    op.execute(
        "CREATE INDEX idx_canonical_entity_ref_team_id "
        "ON canonical_entity(ref_team_id) WHERE ref_team_id IS NOT NULL"
    )

    # ------------------------------------------------------------------
    # Step 4: Lookup table — canonical_participant_roles
    #
    # ``domain_id`` is NULLABLE per ADR-118 V2.38 decision #4 — most roles
    # are domain-scoped, but a small set are cross-domain (future
    # ``yes_side`` etc.).  Composite UNIQUE ``(domain_id, role)`` admits
    # both shapes; PG treats NULL ``domain_id`` rows as distinct.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE canonical_participant_roles (
            id           SERIAL PRIMARY KEY,
            domain_id    INTEGER REFERENCES canonical_event_domains(id) ON DELETE RESTRICT,
            role         TEXT NOT NULL,
            description  TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_canonical_participant_roles_domain_role UNIQUE (domain_id, role)
        )
        """
    )

    # FK-column index on canonical_participant_roles.domain_id (partial —
    # cross-domain rows have NULL ``domain_id``; Glokta carry-forward #2).
    op.execute(
        "CREATE INDEX idx_canonical_participant_roles_domain_id "
        "ON canonical_participant_roles(domain_id) WHERE domain_id IS NOT NULL"
    )

    # Seed participant roles.
    _insert_participant_role_seeds(conn)

    # ------------------------------------------------------------------
    # Step 5: Main typed relation — canonical_event_participants
    #
    # Column shape verbatim from ADR-118 V2.38 lines ~17401-17408.
    # ``canonical_event_id`` ON DELETE CASCADE (event-bound child rows; if
    # an event is deleted, its participants follow).  ``entity_id`` and
    # ``role_id`` ON DELETE RESTRICT (entities and roles outlive any single
    # event).  ``sequence_number`` is NOT NULL with NO default — Glokta
    # carry-forward #5; forces callers to reason about sequence explicitly.
    # Composite UNIQUE ``(canonical_event_id, role_id, sequence_number)``
    # replaces the pre-v2.38 ``UNIQUE (canonical_event_id, role)``; admits
    # the 10-candidate election case where 10 rows share role_id with
    # sequence_number 1..10.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE canonical_event_participants (
            id                  BIGSERIAL PRIMARY KEY,
            canonical_event_id  BIGINT NOT NULL REFERENCES canonical_events(id) ON DELETE CASCADE,
            entity_id           BIGINT NOT NULL REFERENCES canonical_entity(id) ON DELETE RESTRICT,
            role_id             INTEGER NOT NULL REFERENCES canonical_participant_roles(id) ON DELETE RESTRICT,
            sequence_number     INTEGER NOT NULL,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_canonical_event_participants UNIQUE (canonical_event_id, role_id, sequence_number)
        )
        """
    )

    # FK-column indexes on canonical_event_participants (all FK columns NOT
    # NULL → full indexes, no partial WHERE).
    op.execute(
        "CREATE INDEX idx_canonical_event_participants_canonical_event_id "
        "ON canonical_event_participants(canonical_event_id)"
    )
    op.execute(
        "CREATE INDEX idx_canonical_event_participants_entity_id "
        "ON canonical_event_participants(entity_id)"
    )
    op.execute(
        "CREATE INDEX idx_canonical_event_participants_role_id "
        "ON canonical_event_participants(role_id)"
    )


def downgrade() -> None:
    """Reverse 0068: drop in reverse dependency order.

    Drop order (FKs and the trigger dictate the sequence):

        1. ``canonical_event_participants`` — child of canonical_events
           (CASCADE), canonical_entity (RESTRICT), canonical_participant_roles
           (RESTRICT).  Drops first.
        2. ``canonical_participant_roles`` — child of canonical_event_domains
           (RESTRICT).  Drops next.
        3. CONSTRAINT TRIGGER + function on canonical_entity.  CONSTRAINT
           TRIGGER has no ``OR REPLACE`` form, so DROP TRIGGER + DROP
           FUNCTION are explicit (Glokta carry-forward #1 from 0067 review).
        4. ``canonical_entity`` — child of canonical_entity_kinds
           (RESTRICT) and teams (no cascade option; teams outlives this
           migration).  Drops after the trigger so we don't leave a
           dangling trigger pointing at a missing table.
        5. ``canonical_entity_kinds`` — leaf lookup.  Drops last.

    IF EXISTS used throughout for idempotent rollback.  Seed rows drop with
    the tables — no separate DELETE needed.
    """
    # canonical_event_participants — indexes then table.
    op.execute("DROP INDEX IF EXISTS idx_canonical_event_participants_role_id")
    op.execute("DROP INDEX IF EXISTS idx_canonical_event_participants_entity_id")
    op.execute("DROP INDEX IF EXISTS idx_canonical_event_participants_canonical_event_id")
    op.execute("DROP TABLE IF EXISTS canonical_event_participants")

    # canonical_participant_roles — index then table.
    op.execute("DROP INDEX IF EXISTS idx_canonical_participant_roles_domain_id")
    op.execute("DROP TABLE IF EXISTS canonical_participant_roles")

    # CONSTRAINT TRIGGER + function (must drop before canonical_entity table
    # so the trigger object goes away cleanly).  CONSTRAINT TRIGGER has no
    # OR REPLACE — explicit DROP IF EXISTS for both objects.
    op.execute("DROP TRIGGER IF EXISTS trg_canonical_entity_team_backref ON canonical_entity")
    op.execute("DROP FUNCTION IF EXISTS enforce_canonical_entity_team_backref()")

    # canonical_entity — indexes then table.
    op.execute("DROP INDEX IF EXISTS idx_canonical_entity_ref_team_id")
    op.execute("DROP INDEX IF EXISTS idx_canonical_entity_entity_kind_id")
    op.execute("DROP TABLE IF EXISTS canonical_entity")

    # canonical_entity_kinds — leaf lookup.
    op.execute("DROP TABLE IF EXISTS canonical_entity_kinds")
