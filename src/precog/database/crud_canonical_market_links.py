"""CRUD operations for canonical_market_links.

Cohort 3 of the canonical-layer foundation (ADR-118 v2.41 amendment, session
78 capture, Cohort 3 amendment + session 80 S82 design-stage P41 council).
Sister module to ``crud_canonical_markets.py`` and ``crud_canonical_event_links.py``;
uses the same raw-psycopg2 + ``get_cursor`` / ``fetch_one`` + RealDictCursor +
heavy-docstring conventions.

Tables covered:
    - ``canonical_market_links`` (Migration 0072) — bridges the canonical
      market identity tier (``canonical_markets``) to the platform-tier
      ``markets`` table under a state machine governed by ``link_state IN
      ('active','retired','quarantined')``.  See Migration 0072 docstring
      for the full DDL rationale and the Cohort 3 amendment decisions.

Pattern 14 5-step bundle status:
    This module is **step 3a of 5** for the Cohort 3 slot-0072 bundle.
    Step 1 = Migration 0072; step 2 (SQLAlchemy ORM model) is **N/A**
    because Precog uses raw psycopg2 only (no SQLAlchemy ORM despite
    CLAUDE.md's Tech Stack line); step 3a = this module; step 3b =
    ``crud_canonical_event_links.py``; step 4 =
    ``tests/unit/database/test_crud_canonical_market_links_unit.py`` +
    ``tests/unit/database/test_crud_canonical_event_links_unit.py``;
    step 5 = ``tests/integration/database/test_migration_0072_canonical_link_tables.py``.

Phase 1 surface (deliberately minimal — Glokta gap awareness):
    This module ships **read + retire helpers only** — there is intentionally
    NO ``create_link()`` helper in slot 0072.  Per build spec § 8 step 3a:
    the matcher (Cohort 5+) writes through the two-table-write CRUD wrapper
    that lives with slot 0073's ``canonical_match_log`` (Miles consideration
    #3 — atomic INSERT into both link table AND log table in a single
    ``BEGIN ... COMMIT`` transaction).  Adding a thin ``create_link()`` here
    would tempt callers into single-table writes that bypass the audit-log
    invariant.  Slot 0073 ships the wrapper; until then, Phase 1 has no
    live writers.

UPDATE coverage (Cohort 3 deliberate gap):
    This module ships ``retire_link`` (UPDATE link_state='retired' +
    retired_at=now() + retire_reason) but NO general
    ``update_link_metadata()`` or ``update_link()`` helper.  Updates to
    ``algorithm_id`` / ``confidence`` / ``decided_by`` are forbidden by
    convention — re-tuning a link = retire-then-create-new (the same
    immutability pattern the matcher carries from Critical Pattern #6).
    Until a use case justifies otherwise, callers needing UPDATE coverage
    beyond retirement must NOT write ad-hoc UPDATE SQL (Pattern 73
    violation — drift across consumers); file an issue first.

Pattern 73 SSOT discipline:
    The ``link_state`` value vocabulary lives at
    ``src/precog/database/constants.py`` ``LINK_STATE_VALUES``.  This
    module imports from there; it does NOT hardcode the strings.  CRUD
    callers writing ``retire_link`` rely on the literal ``'retired'``
    string in the SQL, but the vocabulary's existence + drift-protection
    is enforced by the constant import at module load.

Reference:
    - ``docs/foundation/ARCHITECTURE_DECISIONS_V2.42.md`` lines ~17707-17717
      (Cohort 3 amendment + DDL + decision rationale)
    - ``src/precog/database/alembic/versions/0072_canonical_link_tables.py``
    - ``src/precog/database/crud_canonical_markets.py`` (style reference)
    - ``src/precog/database/constants.py`` ``LINK_STATE_VALUES``
"""

import logging
from typing import Any, cast

from .connection import fetch_all, fetch_one, get_cursor
from .constants import LINK_STATE_VALUES  # noqa: F401  -- import to assert vocabulary home

logger = logging.getLogger(__name__)


# =============================================================================
# CANONICAL MARKET LINKS — READ OPERATIONS
# =============================================================================


def get_active_link_for_platform_market(
    platform_market_id: int,
) -> dict[str, Any] | None:
    """
    Get the (at-most-one) active canonical_market_links row for a platform market.

    This is the canonical lookup for cross-platform identity resolution at the
    market tier: when a downstream consumer asks "what's the canonical market
    for this platform-tier market row?", they call this function.  The
    ``canonical_market_links.uq_canonical_market_links_active`` partial EXCLUDE
    constraint guarantees at most one ``active`` link per ``platform_market_id``,
    so this function returns either a single row or ``None`` — never multiple.

    Args:
        platform_market_id: Integer FK target into the platform ``markets``
            table (``markets.id``).

    Returns:
        Full ``canonical_market_links`` row dict if an active link exists,
        ``None`` if no active link is found (either no link at all, or all
        existing links are in ``retired`` / ``quarantined`` state).
        Keys: id, canonical_market_id, platform_market_id, link_state,
            confidence, algorithm_id, decided_by, decided_at, retired_at,
            retire_reason, created_at, updated_at

    Example:
        >>> link = get_active_link_for_platform_market(platform_market_id=42)
        >>> if link:
        ...     print(f"Canonical market id={link['canonical_market_id']}")
        ... else:
        ...     print("No active canonical link for this platform market")

    Educational Note:
        The ``link_state = 'active'`` filter is load-bearing: the underlying
        partial-index (the EXCLUDE constraint's index) is the cheapest path
        to this lookup AND the partial filter ensures at-most-one semantics
        downstream consumers can rely on.

        The matcher (Cohort 5+) writes new ``active`` rows via the slot-0073
        two-table-write wrapper.  When an existing active link must be
        replaced, the matcher first retires the old link (this module's
        ``retire_link()``), then inserts a new active link — never updates
        in place.  This per-row immutability simplifies audit-log reasoning.

    Reference:
        - Migration 0072 (table DDL + EXCLUDE constraint)
        - ``crud_canonical_markets.get_canonical_for_platform_market()``
          (sibling helper that JOINs through this table to surface the
          canonical_markets row directly; will be implemented when slot 0072
          lands).
        - ADR-118 v2.41 amendment Cohort 3 design council L6 + L7
    """
    query = """
        SELECT id, canonical_market_id, platform_market_id, link_state,
               confidence, algorithm_id, decided_by, decided_at, retired_at,
               retire_reason, created_at, updated_at
        FROM canonical_market_links
        WHERE platform_market_id = %s
          AND link_state = 'active'
    """
    return fetch_one(query, (platform_market_id,))


def get_link_by_id(link_id: int) -> dict[str, Any] | None:
    """
    Get a canonical_market_links row by its surrogate integer PK.

    Args:
        link_id: BIGSERIAL surrogate PK from ``canonical_market_links.id``.

    Returns:
        Full row dict if found, ``None`` otherwise.  Same keys as
        ``get_active_link_for_platform_market``.

    Example:
        >>> row = get_link_by_id(7)
        >>> if row:
        ...     print(row["link_state"])  # 'active' / 'retired' / 'quarantined'

    Educational Note:
        Lookup by surrogate PK is the cheapest path (single B-tree probe on
        the primary key).  Used primarily by the slot-0073
        ``canonical_match_log.link_id`` JOIN path and by slot-0074 review
        flows that need to surface a specific link by id.

    Reference:
        - Migration 0072 (table DDL)
        - ``crud_canonical_markets.get_canonical_market_by_id()`` (sibling
          lookup-by-PK pattern)
    """
    query = """
        SELECT id, canonical_market_id, platform_market_id, link_state,
               confidence, algorithm_id, decided_by, decided_at, retired_at,
               retire_reason, created_at, updated_at
        FROM canonical_market_links
        WHERE id = %s
    """
    return fetch_one(query, (link_id,))


def list_links_for_canonical_market(
    canonical_market_id: int,
) -> list[dict[str, Any]]:
    """
    List all canonical_market_links rows for a given canonical market.

    Returns links in any state (active / retired / quarantined).  Order is
    by ``decided_at DESC`` so the most-recently-decided link surfaces first
    — useful for operator review flows that want "the current state plus
    historical context for this canonical market".

    Args:
        canonical_market_id: BIGSERIAL surrogate PK from ``canonical_markets.id``.

    Returns:
        List of full row dicts (possibly empty).  Same keys as
        ``get_active_link_for_platform_market``.

    Example:
        >>> links = list_links_for_canonical_market(canonical_market_id=42)
        >>> active = [l for l in links if l["link_state"] == "active"]
        >>> retired = [l for l in links if l["link_state"] == "retired"]
        >>> print(f"{len(active)} active, {len(retired)} retired")

    Educational Note:
        Returns ALL link states because operator review flows need history
        ("how many platforms does this canonical market connect to?") not
        just the current active set.  Hot path for the Miles
        operator-alert-query "stale active links" — filter results
        client-side by ``link_state == 'active'`` and ``decided_at < cutoff``.

        The ``idx_canonical_market_links_canonical_market_id`` index makes
        this lookup O(log n) regardless of total link-table size.

    Reference:
        - Migration 0072 (idx_canonical_market_links_canonical_market_id)
        - ADR-118 v2.41 amendment Cohort 3 alert-query catalog (Miles
          consideration #4)
    """
    query = """
        SELECT id, canonical_market_id, platform_market_id, link_state,
               confidence, algorithm_id, decided_by, decided_at, retired_at,
               retire_reason, created_at, updated_at
        FROM canonical_market_links
        WHERE canonical_market_id = %s
        ORDER BY decided_at DESC
    """
    return fetch_all(query, (canonical_market_id,))


# =============================================================================
# CANONICAL MARKET LINKS — RETIRE OPERATION
# =============================================================================


def retire_link(link_id: int, retire_reason: str | None = None) -> bool:
    """
    Retire a canonical_market_links row.

    Sets ``link_state = 'retired'``, ``retired_at = now()``, and
    ``retire_reason = <provided>``.  This is the canonical retirement path
    — callers must NOT write ad-hoc UPDATE SQL touching these columns
    (Pattern 73 violation; consumers would drift).

    Args:
        link_id: BIGSERIAL surrogate PK from ``canonical_market_links.id``.
        retire_reason: Optional operator-readable rationale stored in the
            ``retire_reason VARCHAR(64)`` column.  Examples per build spec § 3:
            ``'platform_delisted'``, ``'algorithm_corrected'``,
            ``'duplicate_canonical'``.  Free-text NULL acceptable for Phase
            1 callers that don't yet have a retirement-rationale taxonomy.

    Returns:
        ``True`` if a row was retired (matched and updated), ``False`` if
        no row matched the given id.

    Example:
        >>> if retire_link(7, retire_reason="platform_delisted"):
        ...     print("Link 7 retired")
        ... else:
        ...     print("Link 7 not found")

    Educational Note:
        The ``updated_at`` column is automatically refreshed by
        ``trg_canonical_market_links_updated_at`` when this UPDATE fires.
        Callers should rely on the trigger; do NOT write ``updated_at``
        directly (Pattern 73 — duplicating trigger behavior in app code).

        After retiring an active link, the EXCLUDE partial-active constraint
        is satisfied for that ``platform_market_id`` and a fresh ``active``
        link can be inserted.  This is the matcher's "replace an existing
        canonical binding" pattern: retire old, insert new (atomic via the
        slot-0073 two-table-write wrapper).

        Idempotent in effect: retiring an already-retired row simply
        refreshes ``retired_at`` to the current timestamp and overwrites
        ``retire_reason``.  If callers need "retire only if not already
        retired" semantics, they should fetch the row first and check
        ``link_state``.

    Reference:
        - Migration 0072 (table DDL + BEFORE UPDATE trigger)
        - ADR-118 v2.41 amendment Cohort 3 design council L6 (link_state
          state machine)
        - Build spec § 3 (retire_reason rationale taxonomy examples)
    """
    query = """
        UPDATE canonical_market_links
        SET link_state = 'retired',
            retired_at = now(),
            retire_reason = %s
        WHERE id = %s
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query, (retire_reason, link_id))
        return cast("bool", cur.rowcount > 0)
