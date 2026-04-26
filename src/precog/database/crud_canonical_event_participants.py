"""CRUD operations for canonical_event_participants (+ canonical_participant_roles
resolver).

Cohort 1B Pattern 14 retro (issue #1021 Slice C) -- the
canonical-event-participants typed relation joins canonical_events to
canonical_entity rows via a discriminator role (the second-tier "Level B"
identity edge from ADR-118 V2.38).  Sister module to
``crud_canonical_events.py`` (this Slice) and ``crud_canonical_entity.py``
(Slice B); mirrors their raw-psycopg2 + ``get_cursor`` / ``fetch_one`` +
RealDictCursor + heavy-docstring conventions verbatim.

Tables covered:
    - ``canonical_event_participants`` (Migration 0068) -- the typed
      relation row.  Composite natural key
      ``(canonical_event_id, role_id, sequence_number)`` per ADR-118 V2.38
      decision #6 (admits the 10-candidate election case where 10 rows
      share role_id with sequence_number 1..10).  See Migration 0068
      docstring for the full DDL rationale and ADR-118 V2.38 decisions.
    - ``canonical_participant_roles`` (lookup, Migration 0068) -- read-only
      resolver helper ``get_canonical_participant_role_id_by_domain_and_role()``
      only.  ``domain_id`` is NULLABLE to admit cross-domain roles per
      ADR-118 V2.38 decision #4.

``sequence_number``-aware INSERT discipline (per #1021 Slice C scope note):
    The composite UNIQUE constraint on
    ``(canonical_event_id, role_id, sequence_number)`` is the SSOT for
    "this participant slot is unique for this role under this event".
    ``sequence_number`` has NO database default -- callers MUST pass an
    explicit value.  Per ADR-118 V2.38 decision #6 (Glokta carry-forward
    #5 from 0067 review) this design forces caller awareness for the
    multi-candidate case (e.g., 10-candidate election: 10 rows with
    role_id='candidate' and sequence_number=1..10).  This CRUD module
    surfaces that discipline as a REQUIRED parameter (no default in the
    Python signature either) -- callers passing the wrong sequence_number
    for a (canonical_event_id, role_id) pair receive
    ``psycopg2.IntegrityError`` from the UNIQUE violation; callers passing
    a sequence_number outside the valid range for their role context
    receive no DB error (the schema accepts any positive integer), so
    sequence_number semantics are an APPLICATION-LAYER contract -- this
    module does not validate.

Pattern 14 5-step bundle status:
    This module is **step 3 of 5** for Slice C of the Cohort 1B retro
    (issue #1021):
        - step 1 = Migration 0068 (already shipped session 71-72 PR #1005);
        - step 2 (SQLAlchemy ORM model) is **N/A** because Precog uses raw
          psycopg2 only (no SQLAlchemy ORM despite CLAUDE.md's Tech Stack
          line) -- mirrors the Cohort 2 ``crud_canonical_markets`` and
          Slice B ``crud_canonical_entity`` deferrals;
        - step 3 = this module;
        - step 4 = ``tests/unit/database/test_crud_canonical_event_participants_unit.py``;
        - step 5 (integration tests) is already covered by
          ``tests/integration/database/test_migration_0068_canonical_entity_foundation.py``
          (#1012 / session 76 PR #1045) -- bundled in Slice C scope per
          #1021 acceptance criteria.

UPDATE / RETIRE coverage (Slice C deliberate gap, mirrors Slice B and
Cohort 2 deferrals):
    This module ships ``create_canonical_event_participant`` + lookup
    helpers ONLY.  No ``update_canonical_event_participant()`` and no
    ``retire_canonical_event_participant()`` are exposed because
    ``canonical_event_participants`` was migrated WITHOUT ``updated_at`` and
    WITHOUT ``retired_at`` columns (verified via Migration 0068 DDL --
    only id, canonical_event_id, entity_id, role_id, sequence_number,
    created_at).  Per Migration 0068's design intent, participant rows are
    immutable post-INSERT: edits to who participates in a canonical event
    require RETIRE-and-RECREATE of the participant rows or full event
    retirement (via ``retire_canonical_event``).  Until a future cohort
    expands the schema, callers that need UPDATE coverage must NOT write
    ad-hoc UPDATE SQL (Pattern 73 violation -- drift across consumers);
    file an issue or add the helper here first.

DELETE coverage:
    No ``delete_canonical_event_participant()`` helper is exposed.  The
    parent ``canonical_events`` row's ON DELETE CASCADE (Migration 0068
    DDL) is the canonical path for cleaning up participant rows: deleting
    the canonical_events row removes its participants automatically.  This
    is deliberate -- individual-participant DELETE would be a Pattern 73
    violation (the cascade rule is the SSOT for "what cleans up
    participants").

Slice C scope (this module) -- exactly these tables:
    - ``canonical_event_participants`` (CRUD: create + 2 lookups);
    - ``canonical_participant_roles`` (read-only resolver helper);
    - NOT covered (separate Slice C module, ``crud_canonical_events.py``):
        * ``canonical_events`` (main canonical event CRUD)
        * ``canonical_event_domains`` + ``canonical_event_types`` (resolvers)
    - NOT covered (already shipped Slice B):
        * ``canonical_entity`` -- ``crud_canonical_entity.py``
        * ``canonical_entity_kinds`` -- resolver in ``crud_canonical_entity.py``
    - NOT covered (already shipped Cohort 2):
        * ``canonical_markets`` -- ``crud_canonical_markets.py``

Reference:
    - ``docs/foundation/ARCHITECTURE_DECISIONS.md`` ADR-118 V2.38+ (Cohort 1
      ratification + V2.40 carry-forward + V2.41 Cohort 3 amendment)
    - ``src/precog/database/alembic/versions/0068_canonical_entity_foundation.py``
    - ``src/precog/database/crud_canonical_markets.py`` (style reference --
      Cohort 2 sibling template)
    - ``src/precog/database/crud_canonical_entity.py`` (Slice B sibling --
      lookup resolver co-location precedent)
    - ``src/precog/database/crud_canonical_events.py`` (Slice C sibling --
      same-PR cross-reference)
    - ``tests/integration/database/test_migration_0068_canonical_entity_foundation.py``
      (#1012 trigger DDL/body coverage)
"""

from typing import Any

from .connection import fetch_one, get_cursor

# =============================================================================
# CANONICAL EVENT PARTICIPANTS OPERATIONS
# =============================================================================


def create_canonical_event_participant(
    canonical_event_id: int,
    entity_id: int,
    role_id: int,
    sequence_number: int,
) -> dict[str, Any]:
    """
    Create a new canonical_event_participants row.

    Canonical event participants are the typed relation rows that join
    ``canonical_events`` to ``canonical_entity`` rows under a discriminator
    role (e.g., the home/away split for a sports game, the 10 candidates in
    an election, the affected_location for a weather event).  Per ADR-118
    V2.38 decision #6, the composite natural key is
    ``(canonical_event_id, role_id, sequence_number)`` -- ``sequence_number``
    is REQUIRED with NO default to force caller awareness for multi-row-
    per-role cases.

    Args:
        canonical_event_id: BIGINT FK into ``canonical_events.id``.  ON
            DELETE CASCADE -- the event going away takes its participant
            rows with it.  Required (NOT NULL).
        entity_id: BIGINT FK into ``canonical_entity.id``.  ON DELETE
            RESTRICT -- entities outlive any single event.  Required (NOT
            NULL).
        role_id: INTEGER FK into ``canonical_participant_roles.id`` (Pattern
            81 lookup; 10 seeded roles in Migration 0068).  Use
            ``get_canonical_participant_role_id_by_domain_and_role()`` to
            resolve from the (domain, role) text composite.  ON DELETE
            RESTRICT.  Required (NOT NULL).
        sequence_number: INTEGER ordinal within ``(canonical_event_id,
            role_id)``.  Required (NOT NULL, no DB default).  For
            single-row-per-role cases (e.g., sports.home / sports.away),
            pass ``1``.  For multi-row-per-role cases (e.g., 10-candidate
            election with 10 rows of role_id='candidate'), pass 1..10 in
            insertion order.  Sequence semantics are application-layer; this
            CRUD function does not validate the value (a negative or
            zero sequence_number passes; only the UNIQUE composite catches
            duplicates).

    Returns:
        Full row dict of the created canonical event participant.  Keys:
            id, canonical_event_id, entity_id, role_id, sequence_number,
            created_at

    Raises:
        psycopg2.IntegrityError: If
            ``(canonical_event_id, role_id, sequence_number)`` already
            exists (UNIQUE violation -- constraint
            ``uq_canonical_event_participants``), ``canonical_event_id``
            does not reference a real ``canonical_events`` row,
            ``entity_id`` does not reference a real ``canonical_entity``
            row, or ``role_id`` does not reference a real
            ``canonical_participant_roles`` row.

    Example (single-row-per-role: sports game home/away):
        >>> from precog.database.crud_canonical_events import (
        ...     get_canonical_event_domain_id_by_domain,
        ... )
        >>> from precog.database.crud_canonical_event_participants import (
        ...     get_canonical_participant_role_id_by_domain_and_role,
        ...     create_canonical_event_participant,
        ... )
        >>> sports_domain_id = get_canonical_event_domain_id_by_domain("sports")
        >>> home_role_id = get_canonical_participant_role_id_by_domain_and_role(
        ...     sports_domain_id, "home"
        ... )
        >>> away_role_id = get_canonical_participant_role_id_by_domain_and_role(
        ...     sports_domain_id, "away"
        ... )
        >>> create_canonical_event_participant(
        ...     canonical_event_id=42,
        ...     entity_id=7,        # canonical_entity for Buffalo Bills
        ...     role_id=home_role_id,
        ...     sequence_number=1,  # single home participant
        ... )
        >>> create_canonical_event_participant(
        ...     canonical_event_id=42,
        ...     entity_id=8,        # canonical_entity for Miami Dolphins
        ...     role_id=away_role_id,
        ...     sequence_number=1,  # single away participant
        ... )

    Example (multi-row-per-role: 10-candidate election):
        >>> politics_domain_id = get_canonical_event_domain_id_by_domain("politics")
        >>> candidate_role_id = get_canonical_participant_role_id_by_domain_and_role(
        ...     politics_domain_id, "candidate"
        ... )
        >>> for seq, candidate_entity_id in enumerate(candidate_entity_ids, start=1):
        ...     create_canonical_event_participant(
        ...         canonical_event_id=99,
        ...         entity_id=candidate_entity_id,
        ...         role_id=candidate_role_id,
        ...         sequence_number=seq,  # 1..10
        ...     )

    Educational Note:
        ``canonical_event_participants`` is the typed-edge tier in the
        canonical hierarchy: ``canonical_events`` (one-side) joins
        ``canonical_entity`` (many-side) through this relation, with the
        edge labeled by ``role_id`` (Pattern 81 lookup).  This shape is
        what makes the canonical layer polymorphic across domains: a sports
        event has home+away participants; a fighting event has fighter_a/
        fighter_b; an election has N candidates + M moderators.

        ``sequence_number`` has NO database default deliberately (Glokta
        carry-forward #5 from 0067 review): forcing the caller to pass
        a value disambiguates the multi-row-per-role case at the call
        site, rather than admitting silent collisions where the default
        would land all participants on sequence_number=1 and trigger
        UNIQUE violations on the second INSERT.

        Why no ``updated_at`` / ``retired_at`` column?  Per Migration 0068
        the participants tier is immutable post-INSERT; edits to
        participation require either RETIRE-and-RECREATE (drop the rows
        and re-INSERT new ones, which only works in transactions because
        the parent canonical_events row's CASCADE rule cleans up the
        whole set on DELETE) or full event retirement via
        ``retire_canonical_event``.

    Reference:
        - Migration 0068 (table DDL + ON DELETE rules)
        - ADR-118 V2.38 decisions #4 (participant_roles shape), #6
          (sequence_number requirement)
        - Glokta carry-forward #5 (sequence_number no-default discipline)
    """
    query = """
        INSERT INTO canonical_event_participants (
            canonical_event_id, entity_id, role_id, sequence_number
        )
        VALUES (%s, %s, %s, %s)
        RETURNING id, canonical_event_id, entity_id, role_id,
                  sequence_number, created_at
    """

    params = (
        canonical_event_id,
        entity_id,
        role_id,
        sequence_number,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row)


def get_canonical_event_participant_by_id(
    canonical_event_participant_id: int,
) -> dict[str, Any] | None:
    """
    Get a canonical_event_participants row by its surrogate integer PK.

    Args:
        canonical_event_participant_id: BIGSERIAL surrogate PK from
            ``canonical_event_participants.id``.

    Returns:
        Full row dict if found, ``None`` otherwise.  Keys:
            id, canonical_event_id, entity_id, role_id, sequence_number,
            created_at

    Example:
        >>> row = get_canonical_event_participant_by_id(7)
        >>> if row:
        ...     print(row["sequence_number"])    # 1 (or N for multi-row-per-role)
        ...     print(row["entity_id"])          # canonical_entity.id

    Educational Note:
        Lookup by surrogate PK is the cheapest path (single B-tree probe on
        the primary key).  For lookup by canonical (event, role, sequence)
        natural identity, use
        ``get_canonical_event_participants_by_event_and_role()`` (or the
        composite-natural-key probe).  For listing all participants of an
        event, see ``list_canonical_event_participants_by_event()``.

    Reference:
        - Migration 0068 (table DDL)
        - ``crud_canonical_markets.get_canonical_market_by_id`` (sibling
          lookup-by-PK pattern)
    """
    query = """
        SELECT id, canonical_event_id, entity_id, role_id, sequence_number,
               created_at
        FROM canonical_event_participants
        WHERE id = %s
    """
    return fetch_one(query, (canonical_event_participant_id,))


def get_canonical_event_participant_by_natural_key(
    canonical_event_id: int,
    role_id: int,
    sequence_number: int,
) -> dict[str, Any] | None:
    """
    Get a canonical_event_participants row by its composite natural key.

    This is the canonical lookup for "do we already have a participant slot
    for this (event, role, sequence) tuple?"  ``(canonical_event_id, role_id,
    sequence_number)`` is the UNIQUE composite natural key on
    ``canonical_event_participants`` (constraint
    ``uq_canonical_event_participants`` -- Migration 0068).  A hit means
    "participant slot already exists, reuse it (or update the entity_id via
    a separate operation if/when that helper lands)"; a miss means "new
    participant slot, the caller should create it".

    Args:
        canonical_event_id: BIGINT FK into ``canonical_events.id``.
        role_id: INTEGER FK into ``canonical_participant_roles.id``.  Use
            ``get_canonical_participant_role_id_by_domain_and_role()`` to
            resolve from the (domain, role) text composite first.
        sequence_number: INTEGER ordinal within (canonical_event_id, role_id).

    Returns:
        Full row dict if found, ``None`` otherwise.  Same keys as
        ``get_canonical_event_participant_by_id``.

    Example:
        >>> row = get_canonical_event_participant_by_natural_key(
        ...     canonical_event_id=42,
        ...     role_id=home_role_id,
        ...     sequence_number=1,
        ... )
        >>> if row is None:
        ...     print("New participant slot -- caller should create it")
        ... else:
        ...     print(f"Existing participant id={row['id']} found")

    Educational Note:
        ``(canonical_event_id, role_id, sequence_number)`` is the UNIQUE
        composite natural identity (constraint
        ``uq_canonical_event_participants``), so this query returns at most
        one row.  The composite UNIQUE index makes the lookup O(log n)
        regardless of table size.

        Note that this lookup does NOT search by ``entity_id`` -- the
        canonical question is "who plays role X with sequence N in event
        Y", not "where does entity Z appear".  For the latter (e.g., "list
        all events where entity Z participated"), a separate helper would
        be required (out of scope for Slice C).

    Reference:
        - Migration 0068 (table DDL -- ``uq_canonical_event_participants``)
        - ADR-118 V2.38 decision #6 (composite natural identity)
    """
    query = """
        SELECT id, canonical_event_id, entity_id, role_id, sequence_number,
               created_at
        FROM canonical_event_participants
        WHERE canonical_event_id = %s AND role_id = %s AND sequence_number = %s
    """
    return fetch_one(query, (canonical_event_id, role_id, sequence_number))


# =============================================================================
# CANONICAL PARTICIPANT ROLES RESOLVER (read-only helper)
# =============================================================================


def get_canonical_participant_role_id_by_domain_and_role(
    domain_id: int | None,
    role: str,
) -> int | None:
    """
    Resolve a ``canonical_participant_roles`` row by ``(domain_id, role)`` ->
    id (read-only).

    The 10 seeded participant roles (sports.home/away,
    fighting.fighter_a/fighter_b, politics.candidate/moderator,
    weather.affected_location, entertainment.nominee/winner/host) are
    Pattern 81 instances (open canonical enum -> lookup table).  Per
    ADR-118 V2.38 decision #4, ``domain_id`` is NULLABLE on this lookup
    table to admit cross-domain roles (future ``yes_side`` etc.); the
    UNIQUE constraint ``uq_canonical_participant_roles_domain_role``
    treats NULL ``domain_id`` rows as distinct (PG semantics for NULL in
    composite UNIQUE).  Callers constructing canonical_event_participants
    rows MUST resolve the (domain, role) text composite to its integer
    FK before INSERT; this helper centralizes that resolution to avoid
    hardcoded integer literals across consumers (Pattern 73 SSOT).

    Args:
        domain_id: Integer FK from ``canonical_event_domains.id`` for
            domain-scoped roles, or ``None`` for cross-domain roles.  Use
            ``crud_canonical_events.get_canonical_event_domain_id_by_domain()``
            to resolve the domain-id from text first.  Pass ``None``
            verbatim for cross-domain rows (PG matches NULL with NULL via
            ``IS NOT DISTINCT FROM`` semantics, which we encode here as
            ``IS NULL`` because the seed schema uses NULL not the SQL
            ``IS NOT DISTINCT FROM`` operator).
        role: Human-readable role string ('home', 'away', 'fighter_a',
            'candidate', ...).  Case-sensitive (matches the seed text
            exactly).

    Returns:
        Integer ``canonical_participant_roles.id`` if the (domain_id, role)
        pair is seeded, ``None`` if no row matches.

    Example (domain-scoped role):
        >>> from precog.database.crud_canonical_events import (
        ...     get_canonical_event_domain_id_by_domain,
        ... )
        >>> sports_domain_id = get_canonical_event_domain_id_by_domain("sports")
        >>> home_role_id = get_canonical_participant_role_id_by_domain_and_role(
        ...     sports_domain_id, "home"
        ... )
        >>> if home_role_id is None:
        ...     raise RuntimeError(
        ...         "canonical_participant_roles seed missing (sports, home)"
        ...     )

    Example (cross-domain role -- domain_id=None):
        >>> # When future cross-domain roles ship (e.g., 'yes_side' for
        >>> # binary markets across domains), resolve with domain_id=None:
        >>> yes_side_role_id = get_canonical_participant_role_id_by_domain_and_role(
        ...     None, "yes_side"
        ... )

    Educational Note:
        ``(domain_id, role)`` is the UNIQUE composite natural identity
        (constraint ``uq_canonical_participant_roles_domain_role``), so
        this query returns at most one row.  The query branches on whether
        ``domain_id`` is NULL because PG treats ``WHERE col = NULL`` as
        always-false (three-valued logic) -- the equality form
        ``col = %s`` cannot match NULL rows.  We split the query into two
        forms: ``IS NULL`` for cross-domain rows, ``= %s`` for
        domain-scoped rows.

        Mirrors the ``get_canonical_event_type_id_by_domain_and_type``
        shape from ``crud_canonical_events.py`` (composite-natural-key
        lookup) but adds the NULL branch because Migration 0068 makes
        ``canonical_participant_roles.domain_id`` NULLABLE while
        Migration 0067 makes ``canonical_event_types.domain_id`` NOT
        NULL.

    Reference:
        - Migration 0068 (canonical_participant_roles DDL + 10-row seed)
        - ADR-118 V2.38 decision #4 (Pattern 81 lookup with NULLABLE
          domain_id for cross-domain support)
        - DEVELOPMENT_PATTERNS V1.39 Pattern 81
    """
    if domain_id is None:
        query = """
            SELECT id
            FROM canonical_participant_roles
            WHERE domain_id IS NULL AND role = %s
        """
        row = fetch_one(query, (role,))
    else:
        query = """
            SELECT id
            FROM canonical_participant_roles
            WHERE domain_id = %s AND role = %s
        """
        row = fetch_one(query, (domain_id, role))
    return row["id"] if row is not None else None
