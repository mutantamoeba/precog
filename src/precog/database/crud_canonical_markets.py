"""CRUD operations for canonical_markets.

Cohort 2 of the canonical-layer foundation (ADR-118 V2.39 amendment, session 73
capture, Cohort 2 amendment).  Sister module to ``crud_events.py``; uses the
same raw-psycopg2 + ``get_cursor`` / ``fetch_one`` + RealDictCursor + heavy-
docstring conventions.

Tables covered:
    - ``canonical_markets`` (Migration 0069) â€" the canonical (platform-agnostic)
      market identity row.  See migration docstring for the full DDL rationale
      and the Cohort 2 amendment decisions.

Pattern 14 5-step bundle status:
    This module is **step 3 of 5** for the Cohort 2 bundle (ADR-118 V2.39
    Cohort 2 amendment, Holden Finding 11): step 1 = Migration 0069; step 2
    (SQLAlchemy ORM model) is **N/A** because Precog uses raw psycopg2 only
    (no SQLAlchemy ORM despite CLAUDE.md's Tech Stack line); step 3 = this
    module; step 4 = ``tests/unit/database/test_crud_canonical_markets_unit.py``;
    step 5 (integration tests) is deferred to bundle with #1012's 0067/0068
    work next session.

UPDATE coverage (Cohort 2 deliberate gap, per Glokta Finding 10):
    This module ships ``retire_canonical_market`` (UPDATE retired_at) but NO
    general ``update_canonical_market_metadata()`` or ``update_canonical_market()``
    helper. This is intentional for Cohort 2 -- metadata-enrichment helpers land
    with Cohort 3 (Migration 0072+) when the matcher pipeline begins writing to
    canonical_markets.metadata. Until then, callers needing UPDATE coverage
    beyond retirement must NOT write ad-hoc UPDATE SQL (Pattern 73 violation --
    drift across consumers); file an issue or add the helper here first.

Reference:
    - ``docs/foundation/ARCHITECTURE_DECISIONS_V2.40.md`` lines ~17363-17541
      (Cohort 2 amendment + DDL + decision rationale)
    - ``src/precog/database/alembic/versions/0069_canonical_markets_foundation.py``
    - ``src/precog/database/crud_events.py`` (style reference)
"""

import json
import logging
from typing import Any, cast

from .connection import fetch_one, get_cursor

logger = logging.getLogger(__name__)


# =============================================================================
# CANONICAL MARKETS OPERATIONS
# =============================================================================


def create_canonical_market(
    canonical_event_id: int,
    market_type_general: str,
    outcome_label: str | None,
    natural_key_hash: bytes,
    metadata: dict | None = None,
) -> dict[str, Any]:
    """
    Create a new canonical_markets row.

    Canonical markets are the platform-agnostic identity tier for individual
    market shapes (binary / categorical / scalar) under a parent canonical
    event.  Per-platform market identity is owned by ``canonical_market_links``
    (Migration 0072, Cohort 3) â€" this row is the canonical anchor that
    cross-platform replicas point to.

    Args:
        canonical_event_id: Integer FK into ``canonical_events.id`` (BIGINT).
            ON DELETE RESTRICT â€" settlement-bearing markets cannot be
            silently CASCADE-deleted when their parent canonical_event is
            deleted (per ADR-118 V2.39 Cohort 2 amendment decision #5b).
        market_type_general: Closed-enum string in ``('binary', 'categorical',
            'scalar')`` per the pmxt #964 NormalizedMarket contract.  The DB
            CHECK constraint rejects anything outside this set; callers that
            pass an invalid value will see ``psycopg2.IntegrityError``.
            **NOT** a Pattern 81 lookup â€" explicitly closed by contract per
            Cohort 2 decision #2.
        outcome_label: Optional human-readable outcome label (e.g., "Yes",
            "Chiefs", "Over 45.5").  ``VARCHAR(255)`` â€" intentionally a
            superset of platform ``markets.outcome_label VARCHAR(100)``
            ceiling, providing headroom for non-Kalshi platforms with longer
            labels.
        natural_key_hash: ``BYTEA`` (Python ``bytes``).  Derivation rule is
            APPLICATION-LAYER (deferred to Cohort 5 / Migration 0085 seed
            context); this CRUD function is agnostic to the rule and simply
            persists what the caller provides.  ``UNIQUE`` constraint â€"
            duplicate hashes raise ``psycopg2.IntegrityError``.
        metadata: Optional JSONB dict.  Serialized via ``json.dumps`` (mirrors
            the ``crud_events.create_event()`` metadata convention).

    Returns:
        Full row dict of the created canonical market.  Keys:
            id, canonical_event_id, market_type_general, outcome_label,
            natural_key_hash, metadata, created_at, updated_at, retired_at

    Raises:
        psycopg2.IntegrityError: If ``natural_key_hash`` already exists,
            ``canonical_event_id`` does not reference a real canonical_events
            row, or ``market_type_general`` violates the CHECK constraint.

    Example:
        >>> import hashlib
        >>> nk = hashlib.sha256(b"some|natural|key|inputs").digest()
        >>> row = create_canonical_market(
        ...     canonical_event_id=42,
        ...     market_type_general="binary",
        ...     outcome_label="Yes",
        ...     natural_key_hash=nk,
        ... )
        >>> row["id"]  # BIGSERIAL surrogate PK
        7

    Educational Note:
        ``canonical_markets`` is the SECOND tier in the canonical identity
        hierarchy: ``canonical_events -> canonical_markets -> (Cohort 3:
        canonical_market_links -> platform markets)``.  This row exists once
        per market shape regardless of how many platforms list a replica;
        the per-platform replica edges are stored in
        ``canonical_market_links`` (Migration 0072).

        Three concerns are kept on three distinct columns:
        - ``canonical_events.lifecycle_phase`` â€" "is the bet still meaningful?"
        - platform ``markets.status`` â€" "is the market tradeable on platform X?"
        - ``canonical_markets.retired_at`` â€" "was the canonical identity itself
          retired?" (e.g., this row deprecated in favor of canonical_market_id=42)

        ``updated_at`` is maintained by ``trg_canonical_markets_updated_at``
        (BEFORE UPDATE trigger; see Migration 0069).  Callers should NOT
        write ``updated_at`` themselves â€" the trigger overwrites any value
        they pass on UPDATE, and this CRUD module does not expose
        ``updated_at`` as an INSERT parameter (the column default handles it).

    Reference:
        - ``docs/foundation/ARCHITECTURE_DECISIONS_V2.40.md`` lines ~17363-17541
        - Migration 0069 (table DDL + trigger)
        - ADR-118 V2.39 Cohort 2 amendment decisions #2, #3, #4, #5b
    """
    query = """
        INSERT INTO canonical_markets (
            canonical_event_id, market_type_general, outcome_label,
            natural_key_hash, metadata
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, canonical_event_id, market_type_general, outcome_label,
                  natural_key_hash, metadata, created_at, updated_at, retired_at
    """

    params = (
        canonical_event_id,
        market_type_general,
        outcome_label,
        natural_key_hash,
        json.dumps(metadata) if metadata is not None else None,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row)


def get_canonical_market_by_id(canonical_market_id: int) -> dict[str, Any] | None:
    """
    Get a canonical_markets row by its surrogate integer PK.

    Args:
        canonical_market_id: BIGSERIAL surrogate PK from ``canonical_markets.id``.

    Returns:
        Full row dict if found, ``None`` otherwise.  Keys:
            id, canonical_event_id, market_type_general, outcome_label,
            natural_key_hash, metadata, created_at, updated_at, retired_at

    Example:
        >>> row = get_canonical_market_by_id(7)
        >>> if row:
        ...     print(row["market_type_general"])  # 'binary'
        ...     print(row["retired_at"])           # None (active) or timestamp

    Educational Note:
        Lookup by surrogate PK is the cheapest path (single B-tree probe on
        the primary key).  For lookup by natural identity (cross-platform
        matching), use ``get_canonical_market_by_natural_key_hash()`` which
        hits the ``uq_canonical_markets_nk`` UNIQUE index.

    Reference:
        - Migration 0069 (table DDL)
        - ``crud_events.get_event()`` (sibling lookup-by-PK pattern)
    """
    query = """
        SELECT id, canonical_event_id, market_type_general, outcome_label,
               natural_key_hash, metadata, created_at, updated_at, retired_at
        FROM canonical_markets
        WHERE id = %s
    """
    return fetch_one(query, (canonical_market_id,))


def get_canonical_market_by_natural_key_hash(
    natural_key_hash: bytes,
) -> dict[str, Any] | None:
    """
    Get a canonical_markets row by its natural_key_hash.

    This is the canonical lookup for cross-platform identity resolution: when
    a new platform market is observed, the matching layer (Cohort 5+) computes
    the natural key hash from the market's normalized identity inputs and
    looks up the canonical row via this function.  A hit means "this is a
    cross-platform replica of an existing canonical market"; a miss means
    "this is a new canonical identity, create it".

    Args:
        natural_key_hash: BYTEA hash bytes (typically 32 bytes from sha256).
            Derivation rule is application-layer; this function is agnostic
            to how the hash was computed.

    Returns:
        Full row dict if found, ``None`` otherwise.  Same keys as
        ``get_canonical_market_by_id``.

    Example:
        >>> import hashlib
        >>> nk = hashlib.sha256(b"some|natural|key|inputs").digest()
        >>> row = get_canonical_market_by_natural_key_hash(nk)
        >>> if row is None:
        ...     print("New canonical identity â€" caller should create it")
        ... else:
        ...     print(f"Existing canonical id={row['id']} found")

    Educational Note:
        ``natural_key_hash`` is ``UNIQUE`` (constraint
        ``uq_canonical_markets_nk``), so this query returns at most one row.
        The ``UNIQUE`` index makes the lookup O(log n) regardless of table
        size.

        The derivation rule for ``natural_key_hash`` is intentionally
        APPLICATION-LAYER and is being specified separately as part of
        Cohort 5 (Migration 0085 seed context).  This CRUD function is
        a thin lookup that does not validate the hash shape or
        derivation â€" that is the matching layer's responsibility.

    Reference:
        - Migration 0069 (table DDL â€" ``uq_canonical_markets_nk``)
        - ADR-118 V2.39 "natural_key_hash derivation rule (deferral note)"
        - Future: ``src/precog/matching/`` (Cohort 5)
    """
    query = """
        SELECT id, canonical_event_id, market_type_general, outcome_label,
               natural_key_hash, metadata, created_at, updated_at, retired_at
        FROM canonical_markets
        WHERE natural_key_hash = %s
    """
    return fetch_one(query, (natural_key_hash,))


def retire_canonical_market(canonical_market_id: int) -> bool:
    """
    Retire a canonical_markets row by setting ``retired_at = now()``.

    Canonical-tier retirement is the only canonical-tier lifecycle surface on
    ``canonical_markets``: this is for cases where the canonical identity
    itself is deprecated (e.g., this row duplicates an existing canonical
    market and should not be returned by future lookups).  It does NOT
    track per-platform tradability (that's platform ``markets.status``) nor
    event-level state (that's ``canonical_events.lifecycle_phase``).

    Args:
        canonical_market_id: BIGSERIAL surrogate PK from ``canonical_markets.id``.

    Returns:
        ``True`` if a row was retired (matched and updated), ``False`` if no
        row matched the given id.

    Example:
        >>> if retire_canonical_market(7):
        ...     print("Canonical market 7 retired")
        ... else:
        ...     print("Canonical market 7 not found")

    Educational Note:
        ``retired_at`` follows the append-then-retire model used elsewhere in
        the canonical tier (canonical_markets is NOT SCD-2; no
        ``row_current_ind``, no version chain).  Per ADR-118 V2.39 Cohort 2
        amendment Holden Finding 9: this is a deliberate divergence from the
        SCD-2 patterns used on platform-tier tables (Patterns 18, 80) â€" the
        canonical tier is identity, not history.

        The ``updated_at`` column is automatically refreshed by
        ``trg_canonical_markets_updated_at`` when this UPDATE fires.  Callers
        should rely on the trigger; do not write ``updated_at`` directly.

        This function is idempotent in effect: retiring an already-retired
        row simply refreshes ``retired_at`` to the current timestamp.  If
        callers need "retire only if not already retired" semantics, they
        should fetch the row first and check ``retired_at IS NULL``.

    Reference:
        - Migration 0069 (table DDL + trigger)
        - ADR-118 V2.39 Cohort 2 amendment decision #3 (three-distinct-
          concerns model)
        - Holden Finding 9 (canonical_markets is NOT SCD-2)
    """
    query = """
        UPDATE canonical_markets
        SET retired_at = now()
        WHERE id = %s
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query, (canonical_market_id,))
        # cast is load-bearing for mypy: cur.rowcount resolves to Any through
        # the context manager, so `> 0` returns Any. Function is typed -> bool.
        # Looks like a runtime no-op but is the type-narrowing chokepoint here.
        return cast("bool", cur.rowcount > 0)


def get_canonical_for_platform_market(
    platform_market_id: int,
) -> dict[str, Any] | None:
    """
    Resolve the canonical_markets row for a given platform markets row.

    This is the Pattern 73 SSOT helper for the question "give me the canonical
    market that this platform-specific market replicates" â€" encoded as a
    JOIN through ``canonical_market_links`` filtered to ``link_state =
    'active'``.  Centralizing the JOIN here ensures every consumer (matcher,
    pricing, projection, MCP exporters) hits the same query shape; without
    this helper, the JOIN + active-link filter would be duplicated across
    callers and drift over time.

    Per Galadriel Finding 5 (session 73 design review): the helper exists to
    encode the canonical-link semantics ONCE.

    Args:
        platform_market_id: Integer FK target into the platform ``markets``
            table (``markets.id``).

    Returns:
        Full ``canonical_markets`` row dict if an active link exists,
        ``None`` if no active link is found (either no link at all, or the
        link is in a non-active state such as ``proposed`` / ``retired``).

    Raises:
        NotImplementedError: ALWAYS (until Migration 0072 ships).  See note
            below.

    Example:
        >>> # When Migration 0072 ships:
        >>> canonical = get_canonical_for_platform_market(platform_market_id=42)
        >>> if canonical:
        ...     print(f"Canonical market id={canonical['id']}")
        ... else:
        ...     print("No active canonical link for this platform market")

    Note:
        **This helper currently raises NotImplementedError.**  The
        ``canonical_market_links`` table that backs the JOIN does not exist
        yet (it ships in Migration 0072, Cohort 3).  Per ADR-118 V2.39
        Cohort 2 amendment Pattern 14 footnote (Holden Finding 11), the
        helper is defined at-signature now so that:

        1. The Pattern 73 SSOT contract for "give me canonical for this
           market" is published before consumers can begin implementing
           against it (Galadriel Finding 5).
        2. Cohort 3 implementers can drop in the JOIN body without
           changing the public signature or breaking any importer.

        When Migration 0072 lands, the body will become roughly:

        .. code-block:: python

            query = '''
                SELECT cm.id, cm.canonical_event_id, cm.market_type_general,
                       cm.outcome_label, cm.natural_key_hash, cm.metadata,
                       cm.created_at, cm.updated_at, cm.retired_at
                FROM canonical_markets cm
                JOIN canonical_market_links cml
                  ON cml.canonical_market_id = cm.id
                WHERE cml.platform_market_id = %s
                  AND cml.link_state = 'active'
            '''
            return fetch_one(query, (platform_market_id,))

    Reference:
        - ADR-118 V2.39 Cohort 2 amendment Holden Finding 11 (Pattern 14
          5-step bundle footnote)
        - Galadriel Finding 5 (session 73 design memo:
          memory/design_review_cohort2_canonical_markets.md)
        - Future: Migration 0072 (canonical_market_links â€" Cohort 3)
    """
    msg = (
        "get_canonical_for_platform_market() cannot be implemented until "
        "Migration 0072 ships canonical_market_links (Cohort 3).  The helper "
        "is defined at this signature now per ADR-118 V2.39 Cohort 2 "
        "amendment Pattern 14 footnote (Holden Finding 11) so that the "
        "Pattern 73 SSOT contract for 'give me canonical for this market' "
        "(Galadriel Finding 5) is published before consumers can implement "
        "against it.  When Migration 0072 lands, the body becomes a JOIN "
        "through canonical_market_links filtered to link_state = 'active'."
    )
    raise NotImplementedError(msg)
