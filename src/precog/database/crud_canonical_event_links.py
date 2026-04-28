"""CRUD operations for canonical_event_links.

Cohort 3 of the canonical-layer foundation (ADR-118 v2.41 amendment, session
78 capture, Cohort 3 amendment + session 80 S82 design-stage P41 council).
Sister module to ``crud_canonical_events.py`` and
``crud_canonical_market_links.py``; uses the same raw-psycopg2 +
``get_cursor`` / ``fetch_one`` + RealDictCursor + heavy-docstring conventions.

Tables covered:
    - ``canonical_event_links`` (Migration 0072) — bridges the canonical
      event identity tier (``canonical_events``) to the platform-tier
      ``events`` table under a state machine governed by ``link_state IN
      ('active','retired','quarantined')``.  See Migration 0072 docstring
      for the full DDL rationale and the Cohort 3 amendment decisions.

This module is the **structural parallel** of ``crud_canonical_market_links.py``
per L12-L13 (parallelism IS the contract).  Same public surface, same
docstring template, same Phase 1 deliberate gaps; only column names + table
name + FK target differ.

Pattern 14 5-step bundle status:
    Step 3b of 5 for the Cohort 3 slot-0072 bundle (sibling to step 3a =
    ``crud_canonical_market_links.py``).  See that module's docstring for
    the full bundle status; this module's status mirrors it.

Phase 1 surface (deliberately minimal — Glokta gap awareness):
    Read + retire helpers only — there is intentionally NO ``create_link()``
    helper in slot 0072.  Per build spec § 8 step 3b: the matcher (Cohort
    5+) writes through the two-table-write CRUD wrapper that lives with
    slot 0073's ``canonical_match_log`` (Miles consideration #3 — atomic
    INSERT into both link table AND log table in a single ``BEGIN ...
    COMMIT`` transaction).  Adding a thin ``create_link()`` here would
    tempt callers into single-table writes that bypass the audit-log
    invariant.  Slot 0073 ships the wrapper; until then, Phase 1 has no
    live writers.

UPDATE coverage (Cohort 3 deliberate gap):
    Mirrors ``crud_canonical_market_links.py`` discipline — only
    ``retire_link``; no general ``update_link()`` helper.  Re-tuning a
    link = retire-then-create-new (Critical Pattern #6 inheritance).

Pattern 73 SSOT discipline:
    The ``link_state`` value vocabulary lives at
    ``src/precog/database/constants.py`` ``LINK_STATE_VALUES``.  This
    module imports from there; it does NOT hardcode the strings.  The
    same constant covers BOTH ``canonical_market_links.link_state`` AND
    ``canonical_event_links.link_state`` — single vocabulary, two
    enforcement sites.

Reference:
    - ``docs/foundation/ARCHITECTURE_DECISIONS_V2.42.md`` lines ~17707-17717
      (Cohort 3 amendment + DDL + decision rationale)
    - ``src/precog/database/alembic/versions/0072_canonical_link_tables.py``
    - ``src/precog/database/crud_canonical_market_links.py`` (parallel
      module, structural template)
    - ``src/precog/database/constants.py`` ``LINK_STATE_VALUES``
"""

import logging
from typing import Any, cast

from .connection import fetch_all, fetch_one, get_cursor
from .constants import LINK_STATE_VALUES  # noqa: F401  -- import to assert vocabulary home

logger = logging.getLogger(__name__)


# =============================================================================
# CANONICAL EVENT LINKS — READ OPERATIONS
# =============================================================================


def get_active_link_for_platform_event(
    platform_event_id: int,
) -> dict[str, Any] | None:
    """
    Get the (at-most-one) active canonical_event_links row for a platform event.

    Canonical lookup for cross-platform identity resolution at the event
    tier: when a downstream consumer asks "what's the canonical event for
    this platform-tier event row?", they call this function.  The
    ``canonical_event_links.uq_canonical_event_links_active`` partial EXCLUDE
    constraint guarantees at most one ``active`` link per ``platform_event_id``,
    so this function returns either a single row or ``None`` — never multiple.

    Args:
        platform_event_id: Integer FK target into the platform ``events``
            table (``events.id``).

    Returns:
        Full ``canonical_event_links`` row dict if an active link exists,
        ``None`` if no active link is found (either no link at all, or all
        existing links are in ``retired`` / ``quarantined`` state).
        Keys: id, canonical_event_id, platform_event_id, link_state,
            confidence, algorithm_id, decided_by, decided_at, retired_at,
            retire_reason, created_at, updated_at

    Example:
        >>> link = get_active_link_for_platform_event(platform_event_id=42)
        >>> if link:
        ...     print(f"Canonical event id={link['canonical_event_id']}")
        ... else:
        ...     print("No active canonical link for this platform event")

    Educational Note:
        Same load-bearing partial-index reasoning as
        ``crud_canonical_market_links.get_active_link_for_platform_market`` —
        the ``link_state = 'active'`` filter + EXCLUDE constraint's index
        is the cheapest path AND ensures at-most-one semantics.

    Reference:
        - Migration 0072 (table DDL + EXCLUDE constraint)
        - ``crud_canonical_market_links.get_active_link_for_platform_market()``
          (parallel helper for the market tier)
        - ADR-118 v2.41 amendment Cohort 3 design council L6 + L7 + L13
    """
    query = """
        SELECT id, canonical_event_id, platform_event_id, link_state,
               confidence, algorithm_id, decided_by, decided_at, retired_at,
               retire_reason, created_at, updated_at
        FROM canonical_event_links
        WHERE platform_event_id = %s
          AND link_state = 'active'
    """
    return fetch_one(query, (platform_event_id,))


def get_link_by_id(link_id: int) -> dict[str, Any] | None:
    """
    Get a canonical_event_links row by its surrogate integer PK.

    Args:
        link_id: BIGSERIAL surrogate PK from ``canonical_event_links.id``.

    Returns:
        Full row dict if found, ``None`` otherwise.  Same keys as
        ``get_active_link_for_platform_event``.

    Example:
        >>> row = get_link_by_id(7)
        >>> if row:
        ...     print(row["link_state"])  # 'active' / 'retired' / 'quarantined'

    Educational Note:
        Lookup by surrogate PK is the cheapest path (single B-tree probe on
        the primary key).  Used primarily by the slot-0073
        ``canonical_match_log.link_id`` JOIN path — the SET NULL ON DELETE
        rule per ADR-118 v2.42 sub-amendment B means historical match-log
        rows may carry ``link_id IS NULL`` after the underlying link CASCADE-
        deleted; callers must handle the ``None`` return.

    Reference:
        - Migration 0072 (table DDL)
        - ``crud_canonical_market_links.get_link_by_id()`` (parallel helper)
    """
    query = """
        SELECT id, canonical_event_id, platform_event_id, link_state,
               confidence, algorithm_id, decided_by, decided_at, retired_at,
               retire_reason, created_at, updated_at
        FROM canonical_event_links
        WHERE id = %s
    """
    return fetch_one(query, (link_id,))


def list_links_for_canonical_event(
    canonical_event_id: int,
) -> list[dict[str, Any]]:
    """
    List all canonical_event_links rows for a given canonical event.

    Returns links in any state (active / retired / quarantined).  Order is
    by ``decided_at DESC`` so the most-recently-decided link surfaces first
    — useful for operator review flows that want "the current state plus
    historical context for this canonical event".

    Args:
        canonical_event_id: BIGSERIAL surrogate PK from ``canonical_events.id``.

    Returns:
        List of full row dicts (possibly empty).  Same keys as
        ``get_active_link_for_platform_event``.

    Example:
        >>> links = list_links_for_canonical_event(canonical_event_id=42)
        >>> platforms_seen = {l["platform_event_id"] for l in links}
        >>> print(f"Canonical event 42 has linked from {len(platforms_seen)} platform rows")

    Educational Note:
        Returns ALL link states because operator review flows need history.
        Hot path for the Miles operator-alert-query "stale active links" —
        filter results client-side by ``link_state == 'active'`` and
        ``decided_at < cutoff``.

        The ``idx_canonical_event_links_canonical_event_id`` index makes
        this lookup O(log n) regardless of total link-table size.

    Reference:
        - Migration 0072 (idx_canonical_event_links_canonical_event_id)
        - ADR-118 v2.41 amendment Cohort 3 alert-query catalog (Miles
          consideration #4)
    """
    query = """
        SELECT id, canonical_event_id, platform_event_id, link_state,
               confidence, algorithm_id, decided_by, decided_at, retired_at,
               retire_reason, created_at, updated_at
        FROM canonical_event_links
        WHERE canonical_event_id = %s
        ORDER BY decided_at DESC
    """
    return fetch_all(query, (canonical_event_id,))


# =============================================================================
# CANONICAL EVENT LINKS — RETIRE OPERATION
# =============================================================================


def retire_link(link_id: int, retire_reason: str | None = None) -> bool:
    """
    Retire a canonical_event_links row.

    Sets ``link_state = 'retired'``, ``retired_at = now()``, and
    ``retire_reason = <provided>``.  Canonical retirement path — callers
    must NOT write ad-hoc UPDATE SQL touching these columns (Pattern 73
    violation; consumers would drift).

    Args:
        link_id: BIGSERIAL surrogate PK from ``canonical_event_links.id``.
        retire_reason: Optional operator-readable rationale stored in the
            ``retire_reason VARCHAR(64)`` column.  Examples per build spec § 4:
            ``'platform_delisted'``, ``'algorithm_corrected'``,
            ``'duplicate_canonical'``.  Free-text NULL acceptable for Phase
            1 callers.

    Returns:
        ``True`` if a row was retired (matched and updated), ``False`` if
        no row matched the given id.

    Example:
        >>> if retire_link(7, retire_reason="platform_delisted"):
        ...     print("Link 7 retired")
        ... else:
        ...     print("Link 7 not found")

    Educational Note:
        Same ``updated_at`` trigger reasoning as
        ``crud_canonical_market_links.retire_link`` — the
        ``trg_canonical_event_links_updated_at`` BEFORE UPDATE trigger
        refreshes ``updated_at`` automatically.

        After retiring an active link, the EXCLUDE partial-active constraint
        is satisfied for that ``platform_event_id`` and a fresh ``active``
        link can be inserted.  Matcher pattern: retire old, insert new
        (atomic via the slot-0073 two-table-write wrapper).

        Idempotent in effect: retiring an already-retired row simply
        refreshes ``retired_at`` and overwrites ``retire_reason``.

    Reference:
        - Migration 0072 (table DDL + BEFORE UPDATE trigger)
        - ``crud_canonical_market_links.retire_link()`` (parallel helper)
        - ADR-118 v2.41 amendment Cohort 3 design council L6 (link_state
          state machine)
    """
    query = """
        UPDATE canonical_event_links
        SET link_state = 'retired',
            retired_at = now(),
            retire_reason = %s
        WHERE id = %s
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query, (retire_reason, link_id))
        return cast("bool", cur.rowcount > 0)
