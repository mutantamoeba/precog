"""CRUD operations for match_algorithm (Cohort 3 first slot lookup).

Cohort 3 first builder dispatch under #1058 P41 Tier 0 + S82 (synthesis L20 +
L32 + L33 + Elrond E:96-116).  The build spec memo at
``memory/build_spec_0071_holden_memo.md`` is the P41 design-stage artifact for
this slot; this module is **step 3 of the Pattern 14 6-step bundle** scoped in
that memo (step 2 is N/A — Precog uses raw psycopg2 only, no SQLAlchemy ORM).

Tables covered:
    - ``match_algorithm`` (Migration 0071) — the foundation lookup that
      Cohort 3 link tables (``canonical_market_links``,
      ``canonical_event_links``, ``canonical_match_log``) FK INTO via their
      ``algorithm_id`` columns.  Pattern 81 lookup (open enum encoded as
      a table; new algorithms enter via INSERT seeds in their cohort-of-
      origin migration, not ALTER TABLE).

Naming note (no ``canonical_`` prefix — deliberate):
    ``match_algorithm`` is a **foundation** lookup table consumed BY the
    canonical layer, not a member of the canonical-tier surface itself —
    it is referenced FROM canonical-tier tables (``canonical_market_links``,
    ``canonical_event_links``, ``canonical_match_log``), not a canonical-tier
    identity table itself.  Contrast with the Cohort 1 ``canonical_event_
    domains`` / ``canonical_event_types`` lookups, which ARE canonical-tier
    identity tables: their ``canonical_`` prefix scopes canonical-tier
    columns (``canonical_events.event_domain_id`` /
    ``canonical_events.event_type_id``) and the rows themselves are part of
    the canonical-tier identity surface.  ``match_algorithm`` has no
    equivalent scope-binding to a canonical-tier column — it scopes the
    matching machinery, not the identity surface.  Spec memo § 5 row 3 is
    explicit on this naming call.

Critical Pattern #6 (Immutable Versioning) — load-bearing:
    Algorithms are IMMUTABLE post-seed.  Re-tuning a matcher = INSERT a new
    row with a new version (e.g., ``manual_v1`` / ``1.1.0``); the prior row
    stays immutable.  This module ships **read-only** helpers ONLY:

        * ``get_match_algorithm_by_name_version`` (lookup by business key)
        * ``get_default_manual_algorithm`` (Phase 1 default resolver)

    There is NO ``create_match_algorithm`` helper — algorithms enter via
    migration seeds in their cohort-of-origin migration (Phase 1 seed lives
    in Migration 0071; Phase 3+ matchers extend via additional migration
    seeds, not runtime CRUD).  There is NO ``update_match_algorithm`` and
    NO ``delete_match_algorithm`` helper — Critical Pattern #6 immutability.
    There is NO ``retire_match_algorithm`` helper at this slot — the table
    has a ``retired_at`` column but no Phase 1 caller has a use case for
    runtime retirement; if/when that need arises, the helper lands then
    (mirrors the Cohort 2 ``crud_canonical_markets`` deferral discipline of
    only shipping helpers Phase 1 callers actually need).

Pattern 73 (SSOT for code_ref):
    The seeded ``code_ref = 'precog.matching.manual_v1'`` is the canonical
    SSOT pointer Cohort 5+ resolver code uses to locate the matcher
    implementation.  This module surfaces ``code_ref`` in the read result
    dict but does NOT itself import or invoke the module — that is the
    matching layer's responsibility (Cohort 5 deliverable).  See Migration
    0071 docstring for the reservation note.

Pattern 14 6-step bundle status (this module's slot):
    Per build_spec_0071_holden_memo.md § 5:
        * step 1 = Migration 0071 (this PR);
        * step 2 (SQLAlchemy ORM model) is **N/A** because Precog uses raw
          psycopg2 only (mirrors the Cohort 1B + Cohort 2 deferral);
        * step 3 = this module;
        * step 4 = ``tests/unit/database/test_crud_match_algorithm_unit.py``;
        * step 5 = ``tests/integration/database/test_migration_0071_match_algorithm.py``;
        * step 6 = displacement bump in ``crud_canonical_markets.py``
          (10 effective edits, 11 source lines — Migration 0071 → 0072).

Reference:
    - ``memory/build_spec_0071_holden_memo.md`` (Holden S1 design pass —
      the binding spec for this slot)
    - ``memory/design_review_cohort_3_synthesis.md`` L29-L31 (Pattern 81
      lookup lock + code_ref obligation + immutability)
    - ``docs/foundation/ARCHITECTURE_DECISIONS.md`` lines 17621-17628
      (canonical DDL anchor) + v2.41 amendment (Cohort 3 5-slot
      adjudication, session 78)
    - ``src/precog/database/alembic/versions/0071_match_algorithm.py``
      (DDL + seed)
    - ``src/precog/database/crud_canonical_event_participants.py`` and
      ``src/precog/database/crud_canonical_entity.py`` (style reference —
      raw psycopg2 + ``get_cursor`` / ``fetch_one`` + RealDictCursor +
      heavy-docstring conventions)
"""

from typing import Any

from .connection import fetch_one

# =============================================================================
# MATCH ALGORITHM OPERATIONS (read-only — Critical Pattern #6 immutability)
# =============================================================================


def get_match_algorithm_by_name_version(
    name: str,
    version: str,
) -> dict[str, Any] | None:
    """
    Get a match_algorithm row by its (name, version) natural key.

    This is the canonical lookup for resolving an algorithm row from its
    business-key tuple.  ``(name, version)`` is the UNIQUE composite natural
    key on ``match_algorithm`` (constraint ``uq_match_algorithm`` —
    Migration 0071); a hit means "this algorithm version is registered, here
    are its details (including the Pattern 73 ``code_ref`` SSOT pointer)";
    a miss means "the caller asked for an unknown algorithm version".

    Args:
        name: Algorithm family name (e.g., ``'manual_v1'``,
            ``'keyword_jaccard_v1'``, ``'ml_v3'``).  Case-sensitive
            (matches the seed text exactly).
        version: Semver-shaped version string (e.g., ``'1.0.0'``,
            ``'1.1.0'``).  Case-sensitive.

    Returns:
        Full row dict if found, ``None`` otherwise.  Keys:
            id, name, version, code_ref, description, created_at, retired_at

    Example:
        >>> row = get_match_algorithm_by_name_version("manual_v1", "1.0.0")
        >>> if row is None:
        ...     raise RuntimeError("match_algorithm seed missing manual_v1/1.0.0")
        >>> row["code_ref"]  # Pattern 73 SSOT pointer
        'precog.matching.manual_v1'
        >>> row["retired_at"] is None  # active algorithm
        True

    Educational Note:
        ``(name, version)`` is the UNIQUE composite natural identity, so this
        query returns at most one row.  The composite UNIQUE index makes the
        lookup O(log n) regardless of table size.  Algorithms are immutable
        per Critical Pattern #6 — re-tuning a matcher INSERTs a new
        ``(name, version)`` pair rather than UPDATEing the existing row.

        The returned ``code_ref`` is the canonical SSOT pointer the matching
        layer (Cohort 5+) uses to locate the matcher implementation.  This
        function does NOT validate that the module path resolves — that is
        the matching layer's responsibility.

    Reference:
        - Migration 0071 (table DDL + ``uq_match_algorithm`` UNIQUE
          constraint + Phase 1 ``manual_v1`` / ``1.0.0`` seed)
        - ADR-118 v2.40 lines 17621-17628 (canonical DDL anchor)
        - DEVELOPMENT_PATTERNS V1.39 Pattern 81 (lookup tables) + Pattern 73
          (SSOT)
    """
    query = """
        SELECT id, name, version, code_ref, description,
               created_at, retired_at
        FROM match_algorithm
        WHERE name = %s AND version = %s
    """
    return fetch_one(query, (name, version))


def get_default_manual_algorithm() -> dict[str, Any] | None:
    """
    Get the Phase 1 default ``manual_v1`` / ``1.0.0`` algorithm row.

    Phase 1 of the matching pipeline ships exactly one algorithm
    (``manual_v1`` / ``1.0.0``); every link decided manually carries this
    algorithm_id.  This helper is the canonical resolver for "give me the
    default Phase 1 manual algorithm row" so Cohort 3+ link writers don't
    encode the ``(name, version)`` tuple inline (Pattern 73 SSOT — the
    business-key constants live in this helper, not duplicated across
    consumers).

    Returns:
        Full row dict for ``manual_v1`` / ``1.0.0`` if seeded, ``None`` if
        the seed is missing (which would indicate Migration 0071 was not
        applied or the seed row was manually deleted).  Keys:
            id, name, version, code_ref, description, created_at, retired_at

    Example:
        >>> row = get_default_manual_algorithm()
        >>> if row is None:
        ...     raise RuntimeError(
        ...         "Phase 1 manual_v1 seed missing — has Migration 0071 been applied?"
        ...     )
        >>> manual_algorithm_id = row["id"]
        >>> # ... use manual_algorithm_id when writing canonical_market_links
        >>> # ... rows under Migration 0072+ once the link tables ship.

    Educational Note:
        The Phase 1 manual matcher is the floor of the Cohort 3 matching
        pipeline: every link starts as a human decision with confidence =
        1.0.  When Phase 3 ships ``keyword_jaccard_v1``, links get a different
        algorithm_id; when Phase 5+ ships ML matchers, those add their own
        algorithm rows.  Re-tuning ``manual_v1`` (e.g., adjusting how
        confidence is computed for human-decided rows) ships as
        ``manual_v1`` / ``1.1.0`` — a NEW row, not an UPDATE of this one
        (Critical Pattern #6).

        This helper centralizes the ``("manual_v1", "1.0.0")`` tuple so a
        future re-tune that bumps the default can be done in ONE place
        (this function's body) rather than across every link-writer in the
        codebase.

    Reference:
        - Migration 0071 (Phase 1 seed)
        - ADR-118 v2.40 line 17628 + Phase 1 commitments line ~17929
          ("Phase 1 seeds exactly one row: ('manual_v1', '1.0.0')")
        - ``memory/build_spec_0071_holden_memo.md`` § 3 (canonical seed
          spec)
    """
    return get_match_algorithm_by_name_version("manual_v1", "1.0.0")
