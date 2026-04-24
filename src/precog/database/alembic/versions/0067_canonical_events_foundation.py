"""Cohort 1A — canonical identity foundation (Phase B.5 ADR-118).

Introduces the canonical event tier — the first concrete implementation of the
"Level B" canonical identity layer from ADR-118 V2.38 (v2.38 amendment, session
72 capture, issue #996).  This migration is PR B of the Cohort 1 arc; migration
0068 (PR C) lands the canonical entity tier + participant relation.

Scope of 0067 (three tables, two seeded lookups):

    1. ``canonical_event_domains`` (lookup) — 7 seed rows: sports, politics,
       weather, econ, news, entertainment, fighting.  Open-enum encoded as a
       lookup table instead of a CHECK constraint — new domains land as INSERT
       rows, not ALTER TABLE (Pattern 81 candidate; ADR-118 V2.38 decision #2).
    2. ``canonical_event_types`` (lookup) — composite ``(domain_id, event_type)``
       UNIQUE.  Seeds ~13 per-domain event types per ADR-118 V2.38 authoritative
       list (sports: game, match; politics: election, debate, referendum;
       weather: storm_track, temperature_range; econ: earnings_release,
       rate_decision; news: pandemic_case, conflict_outcome; entertainment:
       award_winner, box_office_result).  NO ``fighting`` event_types seeded —
       the ``fighting`` domain exists so ``canonical_participant_roles`` (in
       0068) can reference it, but first fighting-event type lands with the
       first fighting market.  INSERT-not-ALTER discipline.
    3. ``canonical_events`` (main) — the canonical event row.  Column shape is
       verbatim from ADR-118 V2.38 lines ~17332-17348; FK into the two lookup
       tables above replaces the pre-v2.38 CHECK constraints on string
       ``domain`` and ``event_type`` columns.  ``game_id`` and ``series_id``
       are NULLABLE FKs: the canonical layer is a superset of the platform-
       sports ``games`` dimension, not a slave to it.  ``lifecycle_phase``
       defaults to ``'proposed'`` per Phase B.5 state machine.  The
       ``natural_key_hash`` column derivation rule is intentionally APPLICATION-
       LAYER (see ``src/precog/matching/`` when that module lands); DDL is
       agnostic.  ``entities_sorted`` is ``INTEGER[]`` WITHOUT an FK constraint
       this migration — ``canonical_entity`` does not exist until 0068.

FK-column indexes (Samwise discipline — ADR omits these; migrations always add
them because planners use them):

    * ``idx_canonical_events_domain_id``
    * ``idx_canonical_events_event_type_id``
    * ``idx_canonical_events_game_id`` — partial WHERE ``game_id IS NOT NULL``
      (typical for optional FKs, keeps the index small for the
      non-sports-domain majority)
    * ``idx_canonical_events_series_id`` — partial WHERE ``series_id IS NOT
      NULL`` (same rationale)
    * ``idx_canonical_event_types_domain_id``

Pattern 73 discipline: seed values are taken verbatim from ADR-118 V2.38 lines
~17421-17422.  No paraphrase, no drift.  If the ADR is amended, this migration
is the one place the seed text lives in code and is what the future seed-only
migrations will extend via INSERT (not ALTER).

Cross-cohort note (carry-forward from session 72 pipeline review):

    Galadriel flagged a composite-PK partition FK hazard for
    ``canonical_observations`` (future Cohort 3 migration 0078): if the
    partitioned table declares ``PRIMARY KEY (id, ingested_at)``, downstream
    single-column FKs like ``game_states.observation_id`` fail without an
    explicit ``UNIQUE (id)`` workaround.  0067 is NOT affected — ``canonical_
    events`` is non-partitioned with a single-column ``BIGSERIAL PRIMARY
    KEY (id)`` — but the hazard must surface in the Cohort 3 ADR amendment
    before migration 0078 lands.  Tracking forward; not a 0067 concern.

Revision ID: 0067
Revises: 0066
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
revision: str = "0067"
down_revision: str = "0066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# =========================================================================
# Seed data (pinned in the migration — ADR-118 V2.38 lines ~17421-17422).
#
# Pattern 73 discipline: these lists are the SINGLE source of truth in code.
# The ADR body names the same values; future seed-only migrations extend by
# INSERT, never by duplication here.  ``id`` is allocated by SERIAL in
# insertion order; downstream JOINs resolve via the business key (``domain``
# / ``event_type`` text), never a hardcoded integer.
# =========================================================================

# 7 base domains, per ADR-118 V2.38 decision #2.  ``fighting`` is last so the
# seed order matches the ADR prose (which lists it last as "the extension
# case"); SERIAL ids remain stable across fresh runs because insertion order
# is fixed.
_DOMAIN_SEED: list[tuple[str, str]] = [
    ("sports", "Sports events (games, matches, tournaments)"),
    ("politics", "Political events (elections, debates, referendums)"),
    ("weather", "Weather events (storm tracks, temperature ranges)"),
    ("econ", "Economic events (earnings releases, rate decisions)"),
    ("news", "News events (pandemic cases, conflict outcomes)"),
    ("entertainment", "Entertainment events (awards, box office outcomes)"),
    ("fighting", "Fighting events (MMA, boxing — Phase 1 placeholder domain)"),
]

# Per-domain event types, per ADR-118 V2.38 decision #3.  ``fighting`` gets
# NO event_types in this migration — the domain exists (for
# ``canonical_participant_roles`` FK in 0068), but the first fighting event
# type lands with the first fighting market (INSERT-not-ALTER discipline).
_EVENT_TYPE_SEED: list[tuple[str, str, str]] = [
    # (domain_key, event_type, description)
    ("sports", "game", "Single sports game / contest"),
    ("sports", "match", "Sports match (often multi-leg or round-based)"),
    ("politics", "election", "Political election outcome"),
    ("politics", "debate", "Political debate event"),
    ("politics", "referendum", "Referendum / ballot measure outcome"),
    ("weather", "storm_track", "Named-storm track / landfall / intensity event"),
    ("weather", "temperature_range", "Temperature range outcome for a period + location"),
    ("econ", "earnings_release", "Corporate earnings release outcome"),
    ("econ", "rate_decision", "Central-bank rate-decision outcome"),
    ("news", "pandemic_case", "Pandemic case-count / public-health outcome"),
    ("news", "conflict_outcome", "Geopolitical conflict outcome"),
    ("entertainment", "award_winner", "Award-show winner outcome"),
    ("entertainment", "box_office_result", "Box-office / ticket-sales outcome"),
]


def _insert_domain_seeds(conn: sa.engine.Connection) -> None:
    """Insert the 7 base domain rows.

    Uses ``ON CONFLICT (domain) DO NOTHING`` for idempotence: rerunning the
    migration on a partially-migrated DB is a no-op rather than a crash.
    """
    for domain, description in _DOMAIN_SEED:
        conn.execute(
            sa.text(
                "INSERT INTO canonical_event_domains (domain, description) "
                "VALUES (:domain, :description) "
                "ON CONFLICT (domain) DO NOTHING"
            ),
            {"domain": domain, "description": description},
        )


def _insert_event_type_seeds(conn: sa.engine.Connection) -> None:
    """Insert the per-domain event_type rows.

    ``domain_id`` resolved via subquery on ``domain`` text — avoids hardcoded
    integer ids that would drift across fresh vs incremental runs.  Uses
    ``ON CONFLICT (domain_id, event_type) DO NOTHING`` for idempotence.
    """
    for domain_key, event_type, description in _EVENT_TYPE_SEED:
        conn.execute(
            sa.text(
                "INSERT INTO canonical_event_types (domain_id, event_type, description) "
                "VALUES ("
                "    (SELECT id FROM canonical_event_domains WHERE domain = :domain_key),"
                "    :event_type,"
                "    :description"
                ") "
                "ON CONFLICT (domain_id, event_type) DO NOTHING"
            ),
            {
                "domain_key": domain_key,
                "event_type": event_type,
                "description": description,
            },
        )


def upgrade() -> None:
    """Create the two canonical-event lookup tables + canonical_events table, seed lookups, add FK indexes."""
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # Step 1: Lookup table — canonical_event_domains
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE canonical_event_domains (
            id          SERIAL PRIMARY KEY,
            domain      TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    # ------------------------------------------------------------------
    # Step 2: Lookup table — canonical_event_types (domain-scoped)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE canonical_event_types (
            id          SERIAL PRIMARY KEY,
            domain_id   INTEGER NOT NULL REFERENCES canonical_event_domains(id) ON DELETE RESTRICT,
            event_type  TEXT NOT NULL,
            description TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_canonical_event_types_domain_type UNIQUE (domain_id, event_type)
        )
        """
    )

    # FK-column index on canonical_event_types.domain_id (full, not partial —
    # domain_id is NOT NULL, so a partial WHERE clause would not reduce size).
    op.execute(
        "CREATE INDEX idx_canonical_event_types_domain_id ON canonical_event_types(domain_id)"
    )

    # ------------------------------------------------------------------
    # Step 3: Seed lookup tables (domains first, then event_types — the
    # event_type seed resolves domain_id via subquery).
    # ------------------------------------------------------------------
    _insert_domain_seeds(conn)
    _insert_event_type_seeds(conn)

    # ------------------------------------------------------------------
    # Step 4: Main table — canonical_events
    #
    # Column shape verbatim from ADR-118 V2.38 lines ~17332-17348.  BIGSERIAL
    # (not SERIAL) because the canonical tier will eventually aggregate
    # cross-platform markets and Phase 4+ event counts can exceed 2^31.
    # ``metadata`` is JSONB WITHOUT a NOT NULL DEFAULT (ADR-118 V2.38 shape)
    # — callers that want the empty-object default set it at INSERT time.
    # ``retired_at`` is NULLABLE (retired rows are rare; a non-NULL value
    # indicates retirement timestamp, NULL means active).
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE canonical_events (
            id                 BIGSERIAL PRIMARY KEY,
            domain_id          INTEGER NOT NULL REFERENCES canonical_event_domains(id) ON DELETE RESTRICT,
            event_type_id      INTEGER NOT NULL REFERENCES canonical_event_types(id)   ON DELETE RESTRICT,
            entities_sorted    INTEGER[] NOT NULL,
            resolution_window  TSTZRANGE NOT NULL,
            resolution_rule_fp BYTEA,
            natural_key_hash   BYTEA NOT NULL,
            title              VARCHAR NOT NULL,
            description        TEXT,
            game_id            INTEGER REFERENCES games(id),
            series_id          INTEGER REFERENCES series(id),
            lifecycle_phase    VARCHAR(32) NOT NULL DEFAULT 'proposed',
            metadata           JSONB,
            created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            retired_at         TIMESTAMPTZ,
            CONSTRAINT uq_canonical_events_nk UNIQUE (natural_key_hash)
        )
        """
    )

    # ------------------------------------------------------------------
    # Step 5: FK-column indexes on canonical_events.
    #
    # ADR omits these (Scheherazade's decision 3 flag, session 71); Samwise
    # always adds FK indexes because query planners use them for joins and
    # RESTRICT cascade checks.  domain_id and event_type_id are NOT NULL so
    # a full index is correct; game_id and series_id are nullable so we use
    # partial WHERE ... IS NOT NULL to avoid bloating on the typical case
    # (non-sports domain rows have NULL game_id + series_id).
    # ------------------------------------------------------------------
    op.execute("CREATE INDEX idx_canonical_events_domain_id ON canonical_events(domain_id)")
    op.execute("CREATE INDEX idx_canonical_events_event_type_id ON canonical_events(event_type_id)")
    op.execute(
        "CREATE INDEX idx_canonical_events_game_id "
        "ON canonical_events(game_id) WHERE game_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_canonical_events_series_id "
        "ON canonical_events(series_id) WHERE series_id IS NOT NULL"
    )


def downgrade() -> None:
    """Reverse 0067: drop canonical_events, then the two lookup tables.

    Drop order matters: ``canonical_events`` FKs both lookup tables via ON
    DELETE RESTRICT, so it must go first.  Within the lookup tables,
    ``canonical_event_types`` FKs ``canonical_event_domains``, so types goes
    before domains.  IF EXISTS used throughout for idempotent rollback.

    Seed rows drop with the tables — no separate DELETE needed.
    """
    # canonical_events indexes (drop first for clarity; DROP TABLE cascades
    # them but explicit drops keep the downgrade readable).
    op.execute("DROP INDEX IF EXISTS idx_canonical_events_series_id")
    op.execute("DROP INDEX IF EXISTS idx_canonical_events_game_id")
    op.execute("DROP INDEX IF EXISTS idx_canonical_events_event_type_id")
    op.execute("DROP INDEX IF EXISTS idx_canonical_events_domain_id")

    # Main canonical table (must precede the lookups — FK RESTRICT).
    op.execute("DROP TABLE IF EXISTS canonical_events")

    # Lookup tables (types before domains — FK chain).
    op.execute("DROP INDEX IF EXISTS idx_canonical_event_types_domain_id")
    op.execute("DROP TABLE IF EXISTS canonical_event_types")
    op.execute("DROP TABLE IF EXISTS canonical_event_domains")
