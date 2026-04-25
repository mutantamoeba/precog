"""CRUD operations for canonical_entity (+ canonical_entity_kinds resolver).

Cohort 1B Pattern 14 retro (issue #1021 Slice B) -- the canonical-entity tier
is the second concrete implementation of the "Level B" canonical identity
layer from ADR-118 V2.40.  Sister module to ``crud_canonical_markets.py``;
mirrors that module's raw-psycopg2 + ``get_cursor`` / ``fetch_one`` +
RealDictCursor + heavy-docstring conventions verbatim.

Tables covered:
    - ``canonical_entity`` (Migration 0068) -- the canonical (platform-
      agnostic) polymorphic entity row.  Discriminated by
      ``entity_kind_id`` -> ``canonical_entity_kinds`` (Pattern 81 lookup).
      Polymorphic typed back-ref (``ref_team_id`` for entity_kind='team') is
      enforced via the ``trg_canonical_entity_team_backref`` CONSTRAINT
      TRIGGER (Pattern 82 V2 instance).  See Migration 0068 docstring for
      the full DDL rationale and ADR-118 V2.38/V2.40 amendment decisions.
    - ``canonical_entity_kinds`` (lookup, Migration 0068) -- read-only
      resolver helper ``get_canonical_entity_kind_id_by_kind()`` only.

Pattern 82 V2 Forward-Only Direction Policy (CRITICAL DESIGN GUARDRAIL):
    The DB layer (CONSTRAINT TRIGGER ``trg_canonical_entity_team_backref``)
    enforces the polymorphic invariant ``entity_kind='team' => ref_team_id
    NOT NULL``.  The application layer (this CRUD module) **DOES NOT
    pre-validate** that invariant.  Pre-validation here would create a
    second source of truth for the rule; if DB and application drifted, the
    invariant would become ambiguous.  Instead, ``create_canonical_entity()``
    accepts whatever args the caller passes, sends them to the INSERT, and
    lets ``psycopg2.errors.RaiseException`` propagate from the trigger when
    the rule is violated.  The mandatory load-bearing compensating test
    lives at ``tests/database/test_canonical_entity_polymorphic_invariants.py``
    (ADR-118 V2.40 pin -- MUST NOT be retired or skipped).

    Reference: ``docs/guides/DEVELOPMENT_PATTERNS_V1.38.md`` Pattern 82 V2
    "Forward-Only Direction Policy" (lines ~12239-12245) and ADR-118 V2.40
    "Item 4. Pattern 82 V2 Forward-Only Direction Policy + mandatory
    load-bearing regression test (#1011 item 4)" (lines ~17580-17588).

Pattern 14 5-step bundle status:
    This module is **step 3 of 5** for Slice B of the Cohort 1B retro
    (issue #1021):
        - step 1 = Migration 0068 (already shipped session 71-72 PR #1005);
        - step 2 (SQLAlchemy ORM model) is **N/A** because Precog uses raw
          psycopg2 only (no SQLAlchemy ORM despite CLAUDE.md's Tech Stack
          line) -- mirrors the Cohort 2 ``crud_canonical_markets`` deferral;
        - step 3 = this module;
        - step 4 = ``tests/unit/database/test_crud_canonical_entity_unit.py``;
        - step 5 (integration tests) is partially covered by
          ``tests/integration/database/test_migration_0068_canonical_entity_foundation.py``
          (#1012, session 75) PLUS the load-bearing
          ``tests/database/test_canonical_entity_polymorphic_invariants.py``
          (this slice) which exercises the trigger through the CRUD path.

UPDATE / RETIRE coverage (Slice B deliberate gap, mirrors Cohort 2 Glokta
Finding 10 deferral):
    This module ships ``create_canonical_entity`` + lookup helpers ONLY.
    No ``update_canonical_entity()`` and no ``retire_canonical_entity()``
    are exposed because ``canonical_entity`` was migrated WITHOUT
    ``updated_at`` and WITHOUT ``retired_at`` columns (verified via MCP
    against migration 0068 -- see column list in this module's
    ``create_canonical_entity`` docstring).  Any future write surface
    beyond INSERT lands together with:
        - the BEFORE UPDATE trigger retrofit tracked in #1007 (which adds
          a generic ``set_updated_at()`` BEFORE UPDATE trigger, per the
          #1018 claude-review hint), AND
        - whatever lifecycle policy is decided for the canonical-entity
          tier (Cohort 5 / Migration 0085 seed context).
    Until then, callers that need UPDATE coverage must NOT write ad-hoc
    UPDATE SQL (Pattern 73 violation -- drift across consumers); file an
    issue or add the helper here first.

Slice B scope (this module) -- exactly these tables:
    - ``canonical_entity`` (CRUD: create + 2 lookups);
    - ``canonical_entity_kinds`` (read-only resolver helper);
    - NOT covered (deferred to a separate PR under #1021):
        * ``canonical_events`` -- crud_canonical_events.py
        * ``canonical_event_participants`` -- crud_canonical_event_participants.py
        * ``canonical_participant_roles`` + ``canonical_event_domains`` +
          ``canonical_event_types`` -- read-only helpers in crud_lookups.py

Reference:
    - ``docs/foundation/ARCHITECTURE_DECISIONS_V2.40.md`` lines ~17580-17590
      (Pattern 82 V2 Forward-Only Direction Policy ratification)
    - ``docs/guides/DEVELOPMENT_PATTERNS_V1.38.md`` Pattern 82 V2 +
      Pattern 83 (lines ~12117-12302, ~12371)
    - ``src/precog/database/alembic/versions/0068_canonical_entity_foundation.py``
    - ``src/precog/database/crud_canonical_markets.py`` (style reference --
      Cohort 2 sibling template, mirrored line-for-line)
    - ``tests/integration/database/test_migration_0068_canonical_entity_foundation.py``
      (#1012 trigger DDL/body coverage; this CRUD module exercises the
      same trigger through the application boundary)
"""

import json
import logging
from typing import Any

from .connection import fetch_one, get_cursor

logger = logging.getLogger(__name__)


# =============================================================================
# CANONICAL ENTITY OPERATIONS
# =============================================================================


def create_canonical_entity(
    entity_kind_id: int,
    entity_key: str,
    display_name: str,
    ref_team_id: int | None = None,
    metadata: dict | None = None,
) -> dict[str, Any]:
    """
    Create a new canonical_entity row.

    Canonical entities are the platform-agnostic identity tier for individual
    real-world participants in canonical events (teams, fighters, candidates,
    storms, ...).  ``entity_kind_id`` is the Pattern 81 discriminator FK into
    ``canonical_entity_kinds`` (12 seeded kinds; new kinds extend by INSERT,
    not ALTER TABLE).  ``ref_team_id`` is the Pattern 82 typed back-ref into
    the platform-sports ``teams`` dimension -- populated when entity_kind
    resolves to ``'team'``, NULL otherwise.

    **Pattern 82 V2 Forward-Only Direction Policy compliance:** this function
    does NOT pre-validate the polymorphic invariant ``entity_kind='team' =>
    ref_team_id NOT NULL``.  The CONSTRAINT TRIGGER
    ``trg_canonical_entity_team_backref`` is the single source of truth for
    that rule; this CRUD layer trusts the trigger and surfaces
    ``psycopg2.errors.RaiseException`` to callers when the rule is violated.
    Pre-validation here would duplicate the rule (Pattern 73 violation) and
    create ambiguity if DB and application drifted.

    Args:
        entity_kind_id: Integer FK into ``canonical_entity_kinds.id``.
            Resolves at INSERT time inside the trigger via lookup on
            ``canonical_entity_kinds.entity_kind`` text.  Use
            ``get_canonical_entity_kind_id_by_kind()`` to resolve from the
            human-readable kind string ('team', 'fighter', ...).  ON DELETE
            RESTRICT on the FK -- entity_kinds outlive any single entity row.
        entity_key: Stable business identifier for the entity within its
            kind (e.g., the team external_id, the fighter slug).
            Composite UNIQUE with ``entity_kind_id`` via
            ``uq_canonical_entity_kind_key``; duplicate (kind_id, key) pairs
            raise ``psycopg2.IntegrityError``.
        display_name: Human-readable display label (e.g., "Buffalo Bills",
            "Conor McGregor").  NOT NULL.
        ref_team_id: Optional FK into platform-sports ``teams.team_id``.
            **Required when entity_kind='team'** (CONSTRAINT TRIGGER raises
            ``psycopg2.errors.RaiseException`` otherwise).  Must be NULL or
            valid -- a non-NULL value referencing a non-existent
            teams.team_id raises ``psycopg2.IntegrityError`` (FK with ON
            DELETE RESTRICT).  May be safely NULL for non-team entity_kinds
            (the trigger skips non-team rows -- Pattern 82 V2 forward-only).
        metadata: Optional JSONB dict.  Serialized via ``json.dumps``
            (mirrors the ``crud_canonical_markets.create_canonical_market``
            and ``crud_events.create_event`` metadata convention).

    Returns:
        Full row dict of the created canonical entity.  Keys:
            id, entity_kind_id, entity_key, display_name, ref_team_id,
            metadata, created_at

    Raises:
        psycopg2.errors.RaiseException: If the CONSTRAINT TRIGGER
            ``trg_canonical_entity_team_backref`` fires -- specifically when
            ``entity_kind`` resolves to ``'team'`` and ``ref_team_id`` is
            NULL.  Pattern 82 V2 forward-only: this is the canonical
            failure mode; callers MUST NOT pre-validate to avoid this
            (Pattern 73 SSOT compliance).
        psycopg2.IntegrityError: If ``(entity_kind_id, entity_key)`` already
            exists (UNIQUE violation), ``entity_kind_id`` does not reference
            a real ``canonical_entity_kinds`` row, or non-NULL
            ``ref_team_id`` does not reference a real ``teams.team_id``.

    Example:
        >>> # Resolve the entity_kind_id once and reuse:
        >>> team_kind_id = get_canonical_entity_kind_id_by_kind("team")
        >>> # Create a team entity with the required typed back-ref:
        >>> row = create_canonical_entity(
        ...     entity_kind_id=team_kind_id,
        ...     entity_key="BUF-NFL-001",
        ...     display_name="Buffalo Bills",
        ...     ref_team_id=1,  # teams.team_id
        ... )
        >>> row["id"]  # BIGSERIAL surrogate PK
        7

    Example (non-team entity_kind, NULL ref_team_id permitted):
        >>> fighter_kind_id = get_canonical_entity_kind_id_by_kind("fighter")
        >>> row = create_canonical_entity(
        ...     entity_kind_id=fighter_kind_id,
        ...     entity_key="MCGREGOR-CONOR",
        ...     display_name="Conor McGregor",
        ...     ref_team_id=None,  # OK -- trigger skips non-team kinds
        ... )

    Educational Note:
        ``canonical_entity`` is the polymorphic identity tier in the
        canonical hierarchy.  Per ADR-118 V2.38 decision #5, ``ref_team_id``
        is the FIRST typed back-ref column; future kinds will accumulate
        their own typed back-ref columns (e.g., ``ref_fighter_id``,
        ``ref_candidate_id``, ``ref_storm_id``) each with their own
        Pattern 82 V2 CONSTRAINT TRIGGER off the same template.  Adding a
        new typed back-ref means: (a) ALTER TABLE ADD COLUMN, (b) write
        a sibling enforcement function + CONSTRAINT TRIGGER, (c) ship a
        load-bearing regression test in ``tests/database/`` per Pattern 82
        V2's mandatory compensating mechanism.

        Why no ``updated_at`` / ``retired_at`` column?  Per ADR-118 V2.38
        the canonical-entity tier was scoped to identity-creation only in
        Cohort 1B; lifecycle surfaces (UPDATE / RETIRE) defer to a future
        cohort with a dedicated trigger retrofit (#1007 -- generic
        ``set_updated_at()`` BEFORE UPDATE trigger).  Until then, this
        CRUD module exposes INSERT only.

    Reference:
        - ``docs/foundation/ARCHITECTURE_DECISIONS_V2.40.md`` lines
          ~17580-17590 (Pattern 82 V2 Forward-Only Direction Policy)
        - ``docs/guides/DEVELOPMENT_PATTERNS_V1.38.md`` Pattern 82 V2
        - Migration 0068 (table DDL + CONSTRAINT TRIGGER)
        - ADR-118 V2.38 decisions #1, #5; V2.40 amendment Item 4
    """
    query = """
        INSERT INTO canonical_entity (
            entity_kind_id, entity_key, display_name, ref_team_id, metadata
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, entity_kind_id, entity_key, display_name,
                  ref_team_id, metadata, created_at
    """

    params = (
        entity_kind_id,
        entity_key,
        display_name,
        ref_team_id,
        json.dumps(metadata) if metadata is not None else None,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row)


def get_canonical_entity_by_id(canonical_entity_id: int) -> dict[str, Any] | None:
    """
    Get a canonical_entity row by its surrogate integer PK.

    Args:
        canonical_entity_id: BIGSERIAL surrogate PK from ``canonical_entity.id``.

    Returns:
        Full row dict if found, ``None`` otherwise.  Keys:
            id, entity_kind_id, entity_key, display_name, ref_team_id,
            metadata, created_at

    Example:
        >>> row = get_canonical_entity_by_id(7)
        >>> if row:
        ...     print(row["display_name"])  # 'Buffalo Bills'
        ...     print(row["ref_team_id"])   # 1 (or None for non-team kinds)

    Educational Note:
        Lookup by surrogate PK is the cheapest path (single B-tree probe on
        the primary key).  For lookup by canonical (kind, key) natural
        identity, use ``get_canonical_entity_by_kind_and_key()`` which hits
        the ``uq_canonical_entity_kind_key`` UNIQUE composite index.

    Reference:
        - Migration 0068 (table DDL)
        - ``crud_canonical_markets.get_canonical_market_by_id`` (sibling
          lookup-by-PK pattern)
    """
    query = """
        SELECT id, entity_kind_id, entity_key, display_name, ref_team_id,
               metadata, created_at
        FROM canonical_entity
        WHERE id = %s
    """
    return fetch_one(query, (canonical_entity_id,))


def get_canonical_entity_by_kind_and_key(
    entity_kind_id: int,
    entity_key: str,
) -> dict[str, Any] | None:
    """
    Get a canonical_entity row by its (entity_kind_id, entity_key) natural key.

    This is the canonical lookup for "do we already have a canonical entity
    for this (kind, key) tuple?"  ``(entity_kind_id, entity_key)`` is the
    UNIQUE natural composite key on ``canonical_entity`` (constraint
    ``uq_canonical_entity_kind_key`` -- Migration 0068).  A hit means
    "canonical identity already exists, reuse it"; a miss means "new
    canonical identity, the caller should create it".

    Args:
        entity_kind_id: Integer FK from ``canonical_entity_kinds.id``.
            Use ``get_canonical_entity_kind_id_by_kind()`` to resolve from
            the human-readable kind string.
        entity_key: Stable business identifier within the kind.

    Returns:
        Full row dict if found, ``None`` otherwise.  Same keys as
        ``get_canonical_entity_by_id``.

    Example:
        >>> team_kind_id = get_canonical_entity_kind_id_by_kind("team")
        >>> row = get_canonical_entity_by_kind_and_key(team_kind_id, "BUF-NFL-001")
        >>> if row is None:
        ...     print("New canonical identity -- caller should create it")
        ... else:
        ...     print(f"Existing canonical id={row['id']} found")

    Educational Note:
        ``(entity_kind_id, entity_key)`` is the UNIQUE composite natural
        identity (constraint ``uq_canonical_entity_kind_key``), so this
        query returns at most one row.  The composite UNIQUE index makes
        the lookup O(log n) regardless of table size.

        Note that the canonical-entity tier deliberately does NOT use
        ``natural_key_hash`` (the BYTEA hash convention from
        ``canonical_markets``) -- the ``(kind, key)`` text composite is the
        natural identity per ADR-118 V2.38.  Future cross-platform
        identity matching (Cohort 5+) may layer a hash on top via a
        derivation rule, but the canonical lookup remains on the composite.

    Reference:
        - Migration 0068 (table DDL -- ``uq_canonical_entity_kind_key``)
        - ADR-118 V2.38 decision #1 (composite natural identity)
    """
    query = """
        SELECT id, entity_kind_id, entity_key, display_name, ref_team_id,
               metadata, created_at
        FROM canonical_entity
        WHERE entity_kind_id = %s AND entity_key = %s
    """
    return fetch_one(query, (entity_kind_id, entity_key))


# =============================================================================
# CANONICAL ENTITY KINDS RESOLVER (read-only helper)
# =============================================================================


def get_canonical_entity_kind_id_by_kind(entity_kind: str) -> int | None:
    """
    Resolve a ``canonical_entity_kinds.entity_kind`` text -> id (read-only).

    The 12 seeded entity_kinds (team, fighter, candidate, storm, company,
    location, person, product, country, organization, commodity, media) are
    Pattern 81 instances (open canonical enum -> lookup table).  Callers
    constructing canonical_entity rows MUST resolve the human-readable kind
    string to its integer FK before INSERT; this helper centralizes that
    resolution to avoid hardcoded integer literals across consumers
    (Pattern 73 SSOT).

    Args:
        entity_kind: Human-readable kind string ('team', 'fighter', ...).
            Case-sensitive (matches the seed text exactly).

    Returns:
        Integer ``canonical_entity_kinds.id`` if the kind is seeded,
        ``None`` if no row matches the given kind text.

    Example:
        >>> team_kind_id = get_canonical_entity_kind_id_by_kind("team")
        >>> if team_kind_id is None:
        ...     raise RuntimeError("canonical_entity_kinds seed missing 'team'")
        >>> row = create_canonical_entity(
        ...     entity_kind_id=team_kind_id,
        ...     entity_key="BUF-NFL-001",
        ...     display_name="Buffalo Bills",
        ...     ref_team_id=1,
        ... )

    Educational Note:
        This helper is a thin wrapper around a single-row SELECT, returning
        ``None`` (not raising) for unknown kinds.  Pattern 81 lookup tables
        are intended to be extended by INSERT, so callers may legitimately
        encounter a kind that hasn't been seeded yet (in which case the
        right path is to fail loudly with a domain-specific error message,
        not blow up on an unhandled exception inside this helper).

        Future: when canonical_entity_kinds rows are FK-referenced en masse
        (e.g., bulk seeding flows), consider a batch helper that returns
        a {kind: id} dict in a single query.  Out of scope for Slice B.

    Reference:
        - Migration 0068 (canonical_entity_kinds DDL + 12-row seed)
        - ADR-118 V2.38 decision #1 (Pattern 81 lookup table for entity_kinds)
        - DEVELOPMENT_PATTERNS V1.37 Pattern 81
    """
    query = """
        SELECT id
        FROM canonical_entity_kinds
        WHERE entity_kind = %s
    """
    row = fetch_one(query, (entity_kind,))
    return row["id"] if row is not None else None
