"""Shared canonical-market and platform-market seeding helpers for integration tests.

Pattern 73 SSOT extraction (issue #1089, session 81): the canonical-market,
platform-market, canonical-market-link, and match_algorithm helpers were
duplicated byte-near-identically across ``test_migration_0072_canonical_link_tables.py``
and ``test_migration_0073_canonical_match_log.py``.  The slot-0072 file used
``TEST-0072-`` literal prefixes and the slot-0073 file used ``TEST-0073-``;
otherwise the helpers were identical.  Slot 0074 (``canonical_match_overrides``
+ ``canonical_match_reviews``) will need the same helpers, and slot 0075
(``observation_source``) probably will as well.

Glokta P1 review on PR #1090 caught the duplication and recommended extraction
to a shared module before slot 0074 dispatches.  The natural-key uniqueness is
preserved by the uuid-hex ``suffix`` argument; the migration-label literal was
purely cosmetic for grep-discovery and is dropped (suffix alone is sufficient
for grep targeting via ``TEST-``).

The slot-0072 file ALSO has ``_seed_platform_event`` / ``_cleanup_platform_event``
helpers that are NOT shared yet — they're only used by slot 0072.  Those will
extract here when slot 0074 needs them; until then they stay inline.

Convention (matches sibling ``_canonical_event_helpers.py``):
    - Module name has a leading underscore (private/internal-to-tests).
    - Helpers operate via ``get_cursor`` (raw psycopg2) -- mirrors the
      production DB layer; no SQLAlchemy ORM involvement.
    - Caller MUST pair every ``_seed_*(suffix)`` call with the matching
      ``_cleanup_*(returned_id)`` in a finally block (with the
      ``_id = None`` pre-init pattern per #1085 finding #1) so a failed
      test does not leave orphan rows behind.
"""

from __future__ import annotations

import uuid

from precog.database.connection import get_cursor


def _seed_canonical_market(canonical_event_id: int, suffix: str) -> int:
    """Seed a canonical_markets row to back canonical_market_links.canonical_market_id."""
    nk_hash = f"TEST-cm-{suffix}".encode()
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO canonical_markets (
                canonical_event_id, market_type_general, natural_key_hash
            ) VALUES (%s, 'binary', %s)
            RETURNING id
            """,
            (canonical_event_id, nk_hash),
        )
        return int(cur.fetchone()["id"])


def _cleanup_canonical_market(canonical_market_id: int) -> None:
    """Remove a canonical_markets row seeded by _seed_canonical_market."""
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM canonical_markets WHERE id = %s",
            (canonical_market_id,),
        )


def _seed_platform_market(suffix: str) -> int:
    """Seed a platform markets row to back canonical_market_links.platform_market_id."""
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO markets (
                platform_id, event_id, external_id, ticker, title,
                market_type, status, market_key
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                "kalshi",
                None,
                f"TEST-mkt-EXT-{suffix}",
                f"TEST-MKT-{suffix}",
                f"Test platform market ({suffix})",
                "binary",
                "open",
                f"TEMP-{uuid.uuid4()}",
            ),
        )
        return int(cur.fetchone()["id"])


def _cleanup_platform_market(platform_market_id: int) -> None:
    """Remove a platform markets row seeded by _seed_platform_market."""
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM markets WHERE id = %s", (platform_market_id,))


def _seed_canonical_market_link(
    canonical_market_id: int,
    platform_market_id: int,
    algorithm_id: int,
    link_state: str = "active",
    decided_by: str = "system:test",
) -> int:
    """Seed a canonical_market_links row backing link_id / prior_link_id FK targets.

    Parameterized on ``link_state`` (default ``'active'``) and ``decided_by``
    (default ``'system:test'``) per Glokta P2 finding on PR #1090: prior
    slot-0073 helper hard-coded ``'active'``, forcing tests to follow up
    with ``UPDATE ... SET link_state='retired'`` SQL when they wanted a
    retired link.  The parameterization closes that test-shape friction.

    Caller MUST pair with ``_cleanup_canonical_market_link(returned_id)``
    in a finally block.
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO canonical_market_links (
                canonical_market_id, platform_market_id, link_state,
                confidence, algorithm_id, decided_by
            ) VALUES (%s, %s, %s, 1.000, %s, %s)
            RETURNING id
            """,
            (
                canonical_market_id,
                platform_market_id,
                link_state,
                algorithm_id,
                decided_by,
            ),
        )
        return int(cur.fetchone()["id"])


def _cleanup_canonical_market_link(link_id: int) -> None:
    """Remove a canonical_market_links row."""
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM canonical_market_links WHERE id = %s", (link_id,))


def _get_manual_v1_algorithm_id() -> int:
    """Look up the seeded match_algorithm.id for ('manual_v1', '1.0.0').

    Pre-condition assertion: migration 0071 must have shipped the seed row.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id FROM match_algorithm
            WHERE name = 'manual_v1' AND version = '1.0.0'
            """
        )
        row = cur.fetchone()
    assert row is not None, (
        "Pre-condition: match_algorithm seed missing — Migration 0071 should "
        "have populated ('manual_v1', '1.0.0')"
    )
    return int(row["id"])
