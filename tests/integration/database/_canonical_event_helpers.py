"""Shared canonical-event seeding helpers for integration tests.

Pattern 73 SSOT extraction (#1044 item 1) -- the ``_seed_canonical_event``
helper was previously private to ``test_migration_0069_*.py`` and inlined
verbatim in three call sites in ``test_migration_0070_*.py``.  Lifting to
this shared module gives both files a single canonical seed path so the
INSERT shape (FK SELECT subqueries, column list, lifecycle_phase default)
cannot drift across test files.

Convention:
    - Module name has a leading underscore (private/internal-to-tests).
    - Helpers operate via ``get_cursor`` (raw psycopg2) -- mirrors the
      production DB layer; no SQLAlchemy ORM involvement.
    - Caller MUST pair ``_seed_canonical_event(suffix)`` with
      ``_cleanup_canonical_event(returned_id)`` in a finally block so a
      failed test does not leave orphan rows behind.

Issue: #1044 item 1 (Pattern 73 helper extraction)
"""

from __future__ import annotations

from precog.database.connection import get_cursor


def _seed_canonical_event(suffix: str) -> int:
    """Seed a canonical_events row to back the canonical_markets FK.

    Uses the seeded ``sports`` domain + ``game`` event_type from migration 0067.
    Caller MUST pair with ``_cleanup_canonical_event(returned_id)`` in a finally
    block.
    """
    nk_hash = f"TEST-1012-evt-{suffix}".encode()
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO canonical_events (
                domain_id,
                event_type_id,
                entities_sorted,
                resolution_window,
                natural_key_hash,
                title,
                lifecycle_phase
            ) VALUES (
                (SELECT id FROM canonical_event_domains WHERE domain = 'sports'),
                (SELECT et.id FROM canonical_event_types et
                 JOIN canonical_event_domains d ON d.id = et.domain_id
                 WHERE d.domain = 'sports' AND et.event_type = 'game'),
                ARRAY[]::INTEGER[],
                tstzrange(now(), now() + interval '1 day', '[)'),
                %s,
                %s,
                'proposed'
            )
            RETURNING id
            """,
            (nk_hash, f"Test event for 1012 ({suffix})"),
        )
        return int(cur.fetchone()["id"])


def _cleanup_canonical_event(event_id: int) -> None:
    """Delete a canonical_events row seeded by ``_seed_canonical_event``."""
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM canonical_events WHERE id = %s", (event_id,))
