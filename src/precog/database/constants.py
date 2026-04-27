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


LINK_STATE_VALUES: Final[tuple[str, ...]] = (
    "active",
    "retired",
    "quarantined",
)
"""Canonical 3-value vocabulary for ``canonical_market_links.link_state`` and
``canonical_event_links.link_state``.

Authoritative per ADR-118 v2.41 amendment + Cohort 3 design council L5.

Migration 0072 enforces this list at the DDL layer via inline CHECK
constraints on both link tables.  Adding a new state requires lockstep
update of both this constant AND a migration ALTERing the CHECK
constraint on both tables — drift between Python and DDL would produce
silent state-machine bugs (an algorithm-side write of an unknown state
would be rejected by DDL but pass Python validation, or vice versa).

State-machine semantics (S82 council Section 4):
    ``active``       — current canonical-to-platform binding; the
                       EXCLUDE-USING-btree partial index admits at most
                       one ``active`` row per platform-row id.
    ``retired``      — operator-decided reversal of an earlier ``active``;
                       coexists freely with other retired/quarantined rows.
    ``quarantined``  — algorithm-flagged uncertainty pending review;
                       coexists freely; surfaces in operator alert queries.

Per CLAUDE.md Critical Pattern #8 (Pattern 73 SSOT): CRUD modules, state-
machine code, projection writers, and tests MUST import from this constant
rather than hardcoding the string list.

Pattern 81 carve-out: this is intentionally NOT a lookup table.  The state
set is closed (every value binds to code branches per Pattern 81 §
"When NOT to Apply").  See ``Migration 0072`` docstring for the full
carve-out rationale.
"""


POLARITY_VALUES: Final[tuple[str, ...]] = (
    "MUST_MATCH",
    "MUST_NOT_MATCH",
)
"""Canonical 2-value vocabulary for ``canonical_match_overrides.polarity``
(slot 0074, queued).

Pre-positioned in slot 0072 per S82 council Section 4 recommendation: when
slot 0074 lands, the constant is already at its canonical home and the
migration's CHECK constraint can cite the constant from day 1 (rather than
requiring a Pattern 73 retrofit).

Authoritative per ADR-118 v2.41 amendment + Cohort 3 design council L34.

Semantics:
    ``MUST_MATCH``      — operator-asserted positive override; the matcher
                          MUST emit an active link for this (canonical,
                          platform) pair regardless of algorithm score.
    ``MUST_NOT_MATCH``  — operator-asserted negative override; the matcher
                          MUST NOT emit an active link for this pair, even
                          if algorithm score crosses the threshold.

Per CLAUDE.md Critical Pattern #8 (Pattern 73 SSOT): when slot 0074
ships ``canonical_match_overrides``, its CRUD module + tests + state-
machine code MUST import from this constant rather than hardcoding.
"""
