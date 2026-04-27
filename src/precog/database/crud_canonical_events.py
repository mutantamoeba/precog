"""CRUD operations for canonical_events (+ canonical_event_domains and
canonical_event_types resolver helpers).

Cohort 1A Pattern 14 retro (issue #1021 Slice C) -- the canonical-events tier
is the foundational "Level B" canonical identity layer from ADR-118 V2.38.
Sister module to ``crud_canonical_markets.py`` (Cohort 2) and
``crud_canonical_entity.py`` (Slice B); mirrors those modules' raw-psycopg2 +
``get_cursor`` / ``fetch_one`` + RealDictCursor + heavy-docstring conventions
verbatim.

Tables covered:
    - ``canonical_events`` (Migration 0067) -- the canonical (platform-
      agnostic) event row.  Discriminated by ``domain_id`` ->
      ``canonical_event_domains`` and ``event_type_id`` ->
      ``canonical_event_types`` (both Pattern 81 lookups).  ``natural_key_hash``
      is the UNIQUE business identity for cross-platform identity resolution
      (derivation rule is application-layer, deferred to Cohort 5).  See
      Migration 0067 docstring for the full DDL rationale and ADR-118 V2.38
      decisions.
    - ``canonical_event_domains`` (lookup, Migration 0067) -- read-only
      resolver helper ``get_canonical_event_domain_id_by_domain()`` only.
    - ``canonical_event_types`` (lookup, Migration 0067) -- read-only
      resolver helper ``get_canonical_event_type_id_by_domain_and_type()``
      only.  Natural key is the composite ``(domain_id, event_type)``.

Pattern 14 5-step bundle status:
    This module is **step 3 of 5** for Slice C of the Cohort 1A retro
    (issue #1021):
        - step 1 = Migration 0067 (already shipped session 71-72 PR #1003);
        - step 2 (SQLAlchemy ORM model) is **N/A** because Precog uses raw
          psycopg2 only (no SQLAlchemy ORM despite CLAUDE.md's Tech Stack
          line) -- mirrors the Cohort 2 ``crud_canonical_markets`` and
          Slice B ``crud_canonical_entity`` deferrals;
        - step 3 = this module;
        - step 4 = ``tests/unit/database/test_crud_canonical_events_unit.py``;
        - step 5 (integration tests) is already covered by
          ``tests/integration/database/test_migration_0067_canonical_events_foundation.py``
          (#1012 / session 76 PR #1045) -- bundled in Slice C scope per
          #1021 acceptance criteria.

UPDATE / RETIRE coverage (Slice C deliberate gap, mirrors Cohort 2 Glokta
Finding 10 and Slice B deferrals):
    This module ships ``create_canonical_event`` + ``retire_canonical_event``
    + lookup helpers.  ``canonical_events`` was migrated WITH ``updated_at``
    and ``retired_at`` columns (verified via Migration 0067 column list:
    id, domain_id, event_type_id, entities_sorted, resolution_window,
    resolution_rule_fp, natural_key_hash, title, description, game_id,
    series_id, lifecycle_phase, metadata, created_at, updated_at,
    retired_at), so the canonical-tier ``retire_X`` verb is in scope.  No
    general ``update_canonical_event_metadata()`` or ``update_canonical_event()``
    helper -- metadata-enrichment helpers land with Cohort 5+ when the
    matcher pipeline begins writing to ``canonical_events.metadata``.  Until
    then, callers needing UPDATE coverage beyond retirement must NOT write
    ad-hoc UPDATE SQL (Pattern 73 violation -- drift across consumers); file
    an issue or add the helper here first.

Note on ``updated_at`` (BEFORE UPDATE trigger status -- #1007):
    ``canonical_events.updated_at`` was migrated with ``DEFAULT now()`` but
    Migration 0067 did NOT install a generic BEFORE UPDATE trigger to
    refresh it on UPDATE -- the column is currently a static creation
    timestamp.  ``retire_canonical_event`` therefore writes ``retired_at =
    now()`` ONLY (mirrors the deliberate Cohort 2 Pattern 73 carve-out for
    canonical_markets, where the BEFORE UPDATE trigger DOES exist via
    ``trg_canonical_markets_updated_at``).  When #1007 (the generic
    ``set_updated_at()`` BEFORE UPDATE trigger retrofit) ships, this
    function's behavior automatically picks up the trigger via the existing
    UPDATE statement -- no helper-level change required (Pattern 73 SSOT:
    the trigger is the canonical source for ``updated_at`` semantics; this
    module trusts it once installed).

Slice C scope (this module) -- exactly these tables:
    - ``canonical_events`` (CRUD: create + 2 lookups + retire);
    - ``canonical_event_domains`` (read-only resolver helper);
    - ``canonical_event_types`` (read-only resolver helper);
    - NOT covered (separate Slice C module, ``crud_canonical_event_participants.py``):
        * ``canonical_event_participants`` (typed relation CRUD)
        * ``canonical_participant_roles`` (read-only resolver helper)
    - NOT covered (already shipped Slice B):
        * ``canonical_entity`` -- ``crud_canonical_entity.py``
        * ``canonical_entity_kinds`` -- resolver in ``crud_canonical_entity.py``
    - NOT covered (already shipped Cohort 2):
        * ``canonical_markets`` -- ``crud_canonical_markets.py``

Reference:
    - ``docs/foundation/ARCHITECTURE_DECISIONS.md`` ADR-118 V2.38+ (Cohort 1
      ratification + V2.40 carry-forward + V2.41 Cohort 3 amendment)
    - ``src/precog/database/alembic/versions/0067_canonical_events_foundation.py``
    - ``src/precog/database/crud_canonical_markets.py`` (style reference --
      Cohort 2 sibling template, mirrored line-for-line)
    - ``src/precog/database/crud_canonical_entity.py`` (Slice B sibling --
      lookup resolver co-location precedent)
    - ``tests/integration/database/test_migration_0067_canonical_events_foundation.py``
      (#1012 trigger DDL/body coverage)
"""

import json
from typing import Any, cast

from .connection import fetch_one, get_cursor

# =============================================================================
# CANONICAL EVENTS OPERATIONS
# =============================================================================


def create_canonical_event(
    domain_id: int,
    event_type_id: int,
    entities_sorted: list[int],
    resolution_window: str,
    natural_key_hash: bytes,
    title: str,
    description: str | None = None,
    game_id: int | None = None,
    series_id: int | None = None,
    lifecycle_phase: str = "proposed",
    resolution_rule_fp: bytes | None = None,
    metadata: dict | None = None,
) -> dict[str, Any]:
    """
    Create a new canonical_events row.

    Canonical events are the platform-agnostic identity tier for individual
    real-world events (sports games, political elections, weather events,
    earnings releases, ...).  Per ADR-118 V2.38, this row is the canonical
    anchor that cross-platform replicas point to via
    ``canonical_event_links`` (Migration 0072+, Cohort 3).

    Args:
        domain_id: Integer FK into ``canonical_event_domains.id`` (Pattern 81
            lookup; 7 seeded domains in Migration 0067: sports, politics,
            weather, econ, news, entertainment, fighting).  Use
            ``get_canonical_event_domain_id_by_domain()`` to resolve from
            the human-readable domain string.  ON DELETE RESTRICT --
            domains outlive any single event.
        event_type_id: Integer FK into ``canonical_event_types.id`` (Pattern
            81 lookup; ~13 per-domain event types seeded in Migration 0067).
            Use ``get_canonical_event_type_id_by_domain_and_type()`` to
            resolve from the (domain, event_type) text composite.  ON DELETE
            RESTRICT.
        entities_sorted: ``INTEGER[]`` array of canonical_entity ids that
            participate in this event, sorted ascending.  WITHOUT FK
            constraint at the column level (Migration 0067 ships
            ``entities_sorted`` agnostic to ``canonical_entity`` to avoid a
            cross-cohort dependency cycle); callers must ensure the ids
            reference real ``canonical_entity.id`` rows.
        resolution_window: ``TSTZRANGE`` string (e.g.,
            ``"[2026-04-26 12:00+00, 2026-04-26 16:00+00]"``).  Required
            (NOT NULL).  Defines the time interval within which the event
            outcome is determined.
        natural_key_hash: ``BYTEA`` (Python ``bytes``).  Derivation rule is
            APPLICATION-LAYER (deferred to Cohort 5 / Migration 0085 seed
            context); this CRUD function is agnostic to the rule and simply
            persists what the caller provides.  ``UNIQUE`` constraint
            (``uq_canonical_events_nk``) -- duplicate hashes raise
            ``psycopg2.IntegrityError``.
        title: Human-readable event title (e.g., "Buffalo Bills @ Miami
            Dolphins, Week 1").  ``VARCHAR`` -- NOT NULL.
        description: Optional human-readable description.  ``TEXT``.
        game_id: Optional FK into platform-sports ``games.id``.  NULLABLE --
            most non-sports-domain events have NULL ``game_id``.
        series_id: Optional FK into platform-sports ``series.id``.  NULLABLE
            -- mirrors ``game_id`` semantics.
        lifecycle_phase: Closed-enum-like string.  Defaults to ``'proposed'``
            per ADR-118 V2.38 Phase B.5 state machine.  Migration 0067
            ships this as ``VARCHAR(32) NOT NULL DEFAULT 'proposed'`` with
            no inline CHECK; Pattern 84 CHECK retrofit lands separately
            (#1037 / Migration 0070 -- Slice B carry-forward, already
            shipped).
        resolution_rule_fp: Optional ``BYTEA`` fingerprint of the resolution
            rule.  NULLABLE -- most events do not encode a rule fingerprint
            until the matcher pipeline (Cohort 5+) populates it.
        metadata: Optional JSONB dict.  Serialized via ``json.dumps`` (mirrors
            the ``crud_canonical_markets.create_canonical_market`` and
            ``crud_canonical_entity.create_canonical_entity`` metadata
            convention).

    Returns:
        Full row dict of the created canonical event.  Keys:
            id, domain_id, event_type_id, entities_sorted, resolution_window,
            resolution_rule_fp, natural_key_hash, title, description,
            game_id, series_id, lifecycle_phase, metadata, created_at,
            updated_at, retired_at

    Raises:
        psycopg2.IntegrityError: If ``natural_key_hash`` already exists,
            ``domain_id`` / ``event_type_id`` / ``game_id`` / ``series_id``
            do not reference real rows in their target tables, or
            ``resolution_window`` is malformed (PG range parser rejects it).

    Example:
        >>> import hashlib
        >>> from precog.database.crud_canonical_events import (
        ...     get_canonical_event_domain_id_by_domain,
        ...     get_canonical_event_type_id_by_domain_and_type,
        ...     create_canonical_event,
        ... )
        >>> domain_id = get_canonical_event_domain_id_by_domain("sports")
        >>> event_type_id = get_canonical_event_type_id_by_domain_and_type(
        ...     domain_id, "game"
        ... )
        >>> nk = hashlib.sha256(b"NFL|2026-09-04|BUF|MIA").digest()
        >>> row = create_canonical_event(
        ...     domain_id=domain_id,
        ...     event_type_id=event_type_id,
        ...     entities_sorted=[1, 2],  # canonical_entity ids, ascending
        ...     resolution_window="[2026-09-04 17:00+00, 2026-09-04 21:00+00]",
        ...     natural_key_hash=nk,
        ...     title="Buffalo Bills @ Miami Dolphins, Week 1",
        ...     game_id=42,
        ... )
        >>> row["id"]  # BIGSERIAL surrogate PK
        7
        >>> row["lifecycle_phase"]
        'proposed'

    Educational Note:
        ``canonical_events`` is the FIRST tier in the canonical identity
        hierarchy: ``canonical_events -> canonical_markets -> (Cohort 3:
        canonical_market_links -> platform markets)``.  This row exists
        once per real-world event regardless of how many platforms list a
        replica market for it.

        ``lifecycle_phase`` defaults to ``'proposed'`` to encode the Phase
        B.5 state-machine seed state -- the matcher pipeline (Cohort 5+)
        transitions rows to ``'matched'`` / ``'resolved'`` / ``'voided'``
        as the event lifecycle progresses.

        ``updated_at`` is currently a static creation timestamp -- the
        BEFORE UPDATE trigger retrofit lands in #1007.  Once the trigger
        is installed, this column will refresh automatically on every
        UPDATE; callers should NOT write ``updated_at`` themselves either
        before or after the trigger lands (Pattern 73 SSOT compliance).

    Reference:
        - ``docs/foundation/ARCHITECTURE_DECISIONS.md`` ADR-118 V2.38+
        - Migration 0067 (table DDL + lookup seeds)
        - ADR-118 V2.38 decisions #2 (Pattern 81 domain), #3 (Pattern 81
          event_type), #4 (entities_sorted shape), #6 (lifecycle_phase
          default)
    """
    query = """
        INSERT INTO canonical_events (
            domain_id, event_type_id, entities_sorted, resolution_window,
            resolution_rule_fp, natural_key_hash, title, description,
            game_id, series_id, lifecycle_phase, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, domain_id, event_type_id, entities_sorted,
                  resolution_window, resolution_rule_fp, natural_key_hash,
                  title, description, game_id, series_id, lifecycle_phase,
                  metadata, created_at, updated_at, retired_at
    """

    params = (
        domain_id,
        event_type_id,
        entities_sorted,
        resolution_window,
        resolution_rule_fp,
        natural_key_hash,
        title,
        description,
        game_id,
        series_id,
        lifecycle_phase,
        json.dumps(metadata) if metadata is not None else None,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row)


def get_canonical_event_by_id(canonical_event_id: int) -> dict[str, Any] | None:
    """
    Get a canonical_events row by its surrogate integer PK.

    Args:
        canonical_event_id: BIGSERIAL surrogate PK from ``canonical_events.id``.

    Returns:
        Full row dict if found, ``None`` otherwise.  Keys:
            id, domain_id, event_type_id, entities_sorted, resolution_window,
            resolution_rule_fp, natural_key_hash, title, description,
            game_id, series_id, lifecycle_phase, metadata, created_at,
            updated_at, retired_at

    Example:
        >>> row = get_canonical_event_by_id(7)
        >>> if row:
        ...     print(row["title"])             # 'Buffalo Bills @ Miami Dolphins, Week 1'
        ...     print(row["lifecycle_phase"])   # 'proposed' / 'matched' / etc
        ...     print(row["retired_at"])        # None (active) or timestamp

    Educational Note:
        Lookup by surrogate PK is the cheapest path (single B-tree probe on
        the primary key).  For lookup by natural identity (cross-platform
        matching), use ``get_canonical_event_by_natural_key_hash()`` which
        hits the ``uq_canonical_events_nk`` UNIQUE index.

    Reference:
        - Migration 0067 (table DDL)
        - ``crud_canonical_markets.get_canonical_market_by_id`` (sibling
          lookup-by-PK pattern)
    """
    query = """
        SELECT id, domain_id, event_type_id, entities_sorted, resolution_window,
               resolution_rule_fp, natural_key_hash, title, description,
               game_id, series_id, lifecycle_phase, metadata,
               created_at, updated_at, retired_at
        FROM canonical_events
        WHERE id = %s
    """
    return fetch_one(query, (canonical_event_id,))


def get_canonical_event_by_natural_key_hash(
    natural_key_hash: bytes,
) -> dict[str, Any] | None:
    """
    Get a canonical_events row by its natural_key_hash.

    This is the canonical lookup for cross-platform identity resolution: when
    a new platform event is observed, the matching layer (Cohort 5+) computes
    the natural key hash from the event's normalized identity inputs and
    looks up the canonical row via this function.  A hit means "this is a
    cross-platform replica of an existing canonical event"; a miss means
    "this is a new canonical identity, create it".

    Args:
        natural_key_hash: BYTEA hash bytes (typically 32 bytes from sha256).
            Derivation rule is application-layer; this function is agnostic
            to how the hash was computed.

    Returns:
        Full row dict if found, ``None`` otherwise.  Same keys as
        ``get_canonical_event_by_id``.

    Example:
        >>> import hashlib
        >>> nk = hashlib.sha256(b"NFL|2026-09-04|BUF|MIA").digest()
        >>> row = get_canonical_event_by_natural_key_hash(nk)
        >>> if row is None:
        ...     print("New canonical identity -- caller should create it")
        ... else:
        ...     print(f"Existing canonical id={row['id']} found")

    Educational Note:
        ``natural_key_hash`` is ``UNIQUE`` (constraint
        ``uq_canonical_events_nk``), so this query returns at most one row.
        The ``UNIQUE`` index makes the lookup O(log n) regardless of table
        size.

        The derivation rule for ``natural_key_hash`` is intentionally
        APPLICATION-LAYER and is being specified separately as part of
        Cohort 5 (Migration 0085 seed context).  This CRUD function is
        a thin lookup that does not validate the hash shape or
        derivation -- that is the matching layer's responsibility.

    Reference:
        - Migration 0067 (table DDL -- ``uq_canonical_events_nk``)
        - ADR-118 V2.38 "natural_key_hash derivation rule (deferral note)"
        - Future: ``src/precog/matching/`` (Cohort 5)
    """
    query = """
        SELECT id, domain_id, event_type_id, entities_sorted, resolution_window,
               resolution_rule_fp, natural_key_hash, title, description,
               game_id, series_id, lifecycle_phase, metadata,
               created_at, updated_at, retired_at
        FROM canonical_events
        WHERE natural_key_hash = %s
    """
    return fetch_one(query, (natural_key_hash,))


def retire_canonical_event(canonical_event_id: int) -> bool:
    """
    Retire a canonical_events row by setting ``retired_at = now()``.

    Canonical-tier retirement is the only canonical-tier lifecycle surface
    on ``canonical_events``: this is for cases where the canonical identity
    itself is deprecated (e.g., this row duplicates an existing canonical
    event and should not be returned by future lookups).  It does NOT track
    per-platform tradability (that's platform ``markets.status``) nor event-
    matching state (that's ``canonical_events.lifecycle_phase``).

    Args:
        canonical_event_id: BIGSERIAL surrogate PK from ``canonical_events.id``.

    Returns:
        ``True`` if a row was retired (matched and updated), ``False`` if no
        row matched the given id.

    Example:
        >>> if retire_canonical_event(7):
        ...     print("Canonical event 7 retired")
        ... else:
        ...     print("Canonical event 7 not found")

    Educational Note:
        ``retired_at`` follows the append-then-retire model used elsewhere in
        the canonical tier (canonical_events is NOT SCD-2; no
        ``row_current_ind``, no version chain).  Per ADR-118 V2.38 / Cohort 2
        amendment Holden Finding 9 (the same posture for canonical_markets):
        this is a deliberate divergence from the SCD-2 patterns used on
        platform-tier tables (Patterns 18, 80) -- the canonical tier is
        identity, not history.

        Note that ``canonical_events`` does NOT have a ``trg_canonical_events_
        updated_at`` BEFORE UPDATE trigger yet (#1007 retrofit pending).  This
        function therefore writes ``retired_at = now()`` ONLY; ``updated_at``
        will refresh automatically once #1007 ships.  The behavior is forward-
        compatible: when the trigger lands, no helper-level change is needed
        (Pattern 73 SSOT -- the trigger is the canonical source for
        ``updated_at`` semantics; this module trusts it once installed).

        This function is idempotent in effect: retiring an already-retired
        row simply refreshes ``retired_at`` to the current timestamp.  If
        callers need "retire only if not already retired" semantics, they
        should fetch the row first and check ``retired_at IS NULL``.

    Reference:
        - Migration 0067 (table DDL)
        - ``crud_canonical_markets.retire_canonical_market`` (sibling
          retire-tier pattern)
        - #1007 (BEFORE UPDATE trigger retrofit -- forward-pointer)
    """
    query = """
        UPDATE canonical_events
        SET retired_at = now()
        WHERE id = %s
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query, (canonical_event_id,))
        return cast("bool", cur.rowcount > 0)


# =============================================================================
# CANONICAL EVENT DOMAINS RESOLVER (read-only helper)
# =============================================================================


def get_canonical_event_domain_id_by_domain(domain: str) -> int | None:
    """
    Resolve a ``canonical_event_domains.domain`` text -> id (read-only).

    The 7 seeded domains (sports, politics, weather, econ, news,
    entertainment, fighting) are Pattern 81 instances (open canonical enum
    -> lookup table).  Callers constructing canonical_events rows MUST
    resolve the human-readable domain string to its integer FK before
    INSERT; this helper centralizes that resolution to avoid hardcoded
    integer literals across consumers (Pattern 73 SSOT).

    Args:
        domain: Human-readable domain string ('sports', 'politics',
            'weather', 'econ', 'news', 'entertainment', 'fighting').
            Case-sensitive (matches the seed text exactly).

    Returns:
        Integer ``canonical_event_domains.id`` if the domain is seeded,
        ``None`` if no row matches the given domain text.

    Example:
        >>> domain_id = get_canonical_event_domain_id_by_domain("sports")
        >>> if domain_id is None:
        ...     raise RuntimeError("canonical_event_domains seed missing 'sports'")
        >>> # ... use domain_id when calling create_canonical_event()

    Educational Note:
        This helper is a thin wrapper around a single-row SELECT, returning
        ``None`` (not raising) for unknown domains.  Pattern 81 lookup tables
        are intended to be extended by INSERT, so callers may legitimately
        encounter a domain that hasn't been seeded yet (in which case the
        right path is to fail loudly with a domain-specific error message,
        not blow up on an unhandled exception inside this helper).

        Mirrors the ``get_canonical_entity_kind_id_by_kind`` shape from
        ``crud_canonical_entity.py`` -- read-only resolver, ``None`` on miss,
        no caching at this layer (Pattern 81 lookups are small enough that
        a per-call DB hit is fine; if hot-path consumers emerge, a cache
        layer can land separately mirroring ``crud_lookups.py``'s sport/
        league cache shape).

    Reference:
        - Migration 0067 (canonical_event_domains DDL + 7-row seed)
        - ADR-118 V2.38 decision #2 (Pattern 81 lookup table for domains)
        - DEVELOPMENT_PATTERNS V1.39 Pattern 81
    """
    query = """
        SELECT id
        FROM canonical_event_domains
        WHERE domain = %s
    """
    row = fetch_one(query, (domain,))
    return row["id"] if row is not None else None


# =============================================================================
# CANONICAL EVENT TYPES RESOLVER (read-only helper)
# =============================================================================


def get_canonical_event_type_id_by_domain_and_type(
    domain_id: int,
    event_type: str,
) -> int | None:
    """
    Resolve a ``canonical_event_types`` row by ``(domain_id, event_type)`` ->
    id (read-only).

    The ~13 per-domain seeded event_types (sports.game/match,
    politics.election/debate/referendum, weather.storm_track/temperature_range,
    econ.earnings_release/rate_decision, news.pandemic_case/conflict_outcome,
    entertainment.award_winner/box_office_result) are Pattern 81 instances
    (open canonical enum -> lookup table).  The natural identity is the
    composite ``(domain_id, event_type)`` (constraint
    ``uq_canonical_event_types_domain_type`` -- Migration 0067) because
    event_type strings can repeat across domains in principle (currently
    they do not, but the schema admits it).  Callers constructing
    canonical_events rows MUST resolve the (domain, event_type) text
    composite to its integer FK before INSERT; this helper centralizes
    that resolution to avoid hardcoded integer literals across consumers
    (Pattern 73 SSOT).

    Args:
        domain_id: Integer FK from ``canonical_event_domains.id``.  Use
            ``get_canonical_event_domain_id_by_domain()`` to resolve from
            the human-readable domain string first.
        event_type: Human-readable event_type string ('game', 'match',
            'election', 'storm_track', ...).  Case-sensitive (matches
            the seed text exactly).

    Returns:
        Integer ``canonical_event_types.id`` if the (domain_id, event_type)
        pair is seeded, ``None`` if no row matches.

    Example:
        >>> domain_id = get_canonical_event_domain_id_by_domain("sports")
        >>> event_type_id = get_canonical_event_type_id_by_domain_and_type(
        ...     domain_id, "game"
        ... )
        >>> if event_type_id is None:
        ...     raise RuntimeError(
        ...         "canonical_event_types seed missing (sports, game)"
        ...     )
        >>> # ... use event_type_id when calling create_canonical_event()

    Educational Note:
        ``(domain_id, event_type)`` is the UNIQUE composite natural identity
        (constraint ``uq_canonical_event_types_domain_type``), so this query
        returns at most one row.  The composite UNIQUE index makes the
        lookup O(log n) regardless of table size.

        Mirrors the ``get_canonical_entity_by_kind_and_key`` shape from
        ``crud_canonical_entity.py`` (composite-natural-key lookup) but
        returns just the resolved id (not the full row), matching the
        shape of ``get_canonical_entity_kind_id_by_kind`` (single-id
        resolver).  This is the canonical resolver shape for Pattern 81
        lookups whose natural key is a composite.

    Reference:
        - Migration 0067 (canonical_event_types DDL + per-domain seed)
        - ADR-118 V2.38 decision #3 (Pattern 81 lookup table for
          event_types)
        - DEVELOPMENT_PATTERNS V1.39 Pattern 81
    """
    query = """
        SELECT id
        FROM canonical_event_types
        WHERE domain_id = %s AND event_type = %s
    """
    row = fetch_one(query, (domain_id, event_type))
    return row["id"] if row is not None else None
