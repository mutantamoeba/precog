"""Canonical Python source-of-truth constants for the database tier.

Pattern 73 SSOT (CLAUDE.md Critical Pattern #8): any value list appearing
in more than one location MUST have ONE canonical definition + pointers
from the others.  This module is that canonical location for cross-cutting
database vocabulary that future state-machine code, projection views, and
migrations will need to share with DDL constraints.

When to add a constant here:
    - The value(s) are referenced by DDL (CHECK, lookup table, trigger
      function)
    - AND will be referenced by Python code (state-machine transitions,
      projection writers, CRUD functions, validators)
    - AND drift between the two locations would corrupt data or surface
      as silent failures

When NOT to add a constant here:
    - Value is referenced only inside one migration (Pattern 6 — migrations
      are immutable post-ship; no consumer to share with)
    - Value is referenced only in tests (test code defines its own
      fixtures)
"""

from __future__ import annotations

from typing import Final

CANONICAL_EVENT_LIFECYCLE_PHASES: Final[tuple[str, ...]] = (
    "proposed",
    "listed",
    "pre_event",
    "live",
    "suspended",
    "settling",
    "resolved",
    "voided",
)
"""Canonical 8-value vocabulary for ``canonical_events.lifecycle_phase``.

Authoritative per ADR-118 V2.40 Cohort 1 carry-forward item 3.

Migration 0070 (CHECK on ``canonical_events.lifecycle_phase``) and
Migration 0077 (CHECK on ``canonical_event_phase_log.phase``, when it
lands) both enforce this list at the DDL layer.  State-machine transition
code, projection views, and the phase-log consumer MUST import from here
rather than hardcoding string literals (Pattern 73 SSOT).

The tuple ordering reflects the canonical state-machine progression:
``proposed -> listed -> pre_event -> live -> (suspended -> live |
settling -> resolved | voided)``.  Ordering MAY be relied on by consumers
(e.g., phase-precedence comparisons); a future migration that reorders
values MUST update this constant in the same change.

See DEVELOPMENT_PATTERNS V1.38 Pattern 84 for the two-phase
NOT VALID + VALIDATE pattern that any future migration adding similar
vocabulary CHECKs should follow.
"""
