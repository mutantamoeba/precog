"""CRUD operations for canonical_event_phase_log -- THE event-phase audit ledger.

Cohort 4 second slot of the canonical-layer foundation (ADR-118 V2.40
Item 3 + V2.43 Item 2 + session 86 Cohort 4 4-agent design council +
session 87 PM-composed build spec at
``memory/build_spec_0079_pm_memo.md`` + S82 SKIP verdict at
``memory/s82_slot_0079_skip_memo.md``).  Sister module to
``crud_canonical_match_log.py``; uses the same raw-psycopg2 +
``get_cursor`` / ``RealDictCursor`` + heavy-docstring conventions.

Tables covered:
    - ``canonical_event_phase_log`` (Migration 0079) -- append-only audit
      ledger for canonical_events.lifecycle_phase transitions.  Most rows
      are written by the AFTER INSERT OR UPDATE OF lifecycle_phase trigger
      ``trg_canonical_events_log_phase_transition`` (changed_by=
      'system:trigger'); operator-driven manual phase corrections that
      bypass the canonical_events UPDATE path use ``append_phase_transition()``.

THE RESTRICTED API SURFACE -- APPEND-ONLY VIA APPLICATION DISCIPLINE:

    This module exposes EXACTLY ONE write function:
    ``append_phase_transition()``.  There are NO ``update_*`` functions,
    NO ``delete_*`` functions, NO ``upsert_*`` functions.  This is by
    design: the audit ledger is append-only, and the discipline lives in
    this module's API surface (Migration 0079 docstring § "Append-only
    via application discipline").

    The trigger-enforced version (BEFORE UPDATE/DELETE -> RAISE EXCEPTION)
    is queued for slot 0090 after a 30-day production soak validates that
    the application-discipline approach is sufficient (slot 0073
    precedent inheritance).  Until then:

        - DO NOT add ``update_*`` / ``delete_*`` / ``upsert_*`` helpers
          to this module without an ADR amendment.
        - DO NOT write ad-hoc ``UPDATE canonical_event_phase_log`` /
          ``DELETE FROM canonical_event_phase_log`` SQL anywhere outside
          the slot-0079 migration's downgrade (Pattern 73 violation --
          consumers would drift; future S81 grep audits will sweep for
          this).
        - The ``append_phase_transition()`` function is the ONLY sanctioned
          MANUAL write path.  The trigger-driven path (system:trigger rows
          from canonical_events INSERT/UPDATE) is also sanctioned and
          coordinates correctness via the trigger function body.

System-driven vs. operator-driven write paths:

    System-driven (the common case):
        Every INSERT / UPDATE OF lifecycle_phase on ``canonical_events``
        invokes ``trg_canonical_events_log_phase_transition`` which
        INSERTs a row with ``changed_by='system:trigger'``.  This is the
        primary audit-stream populator; operators do not call into this
        module for the common case.

    Operator-driven (rare):
        Manual phase corrections that bypass the canonical_events UPDATE
        path -- e.g., correcting a misclassified phase by directly
        appending an audit row WITHOUT actually changing
        canonical_events.lifecycle_phase.  Use case: a previously-emitted
        phase-log row was wrong because the operator's earlier UPDATE
        used the wrong phase, and the operator wants to record a
        correction in the audit stream.  The function does NOT itself
        update canonical_events; it only writes the audit row.

Pattern 73 SSOT discipline (CLAUDE.md Critical Pattern #8):

    Two vocabularies are SSOT-anchored at
    ``src/precog/database/constants.py``:

        ``CANONICAL_EVENT_LIFECYCLE_PHASES``  -- 8-value lifecycle_phase
                                                 vocabulary mirrored by
                                                 (a) Migration 0070's
                                                 canonical_events.lifecycle_phase
                                                 CHECK and (b) Migration
                                                 0079's two CHECKs on
                                                 ``new_phase`` and
                                                 ``previous_phase``.  This
                                                 module imports the
                                                 constant and uses it in
                                                 real-guard ``ValueError``-
                                                 raising validation in
                                                 ``append_phase_transition()``.

        ``DECIDED_BY_PREFIXES``               -- 3-prefix actor taxonomy
                                                 (``human:`` / ``service:`` /
                                                 ``system:``).  Reused
                                                 from slot 0073 per
                                                 build spec § 8 #2 +
                                                 Pattern 73 SSOT
                                                 discipline.  The trigger
                                                 emits 'system:trigger'
                                                 (system: prefix); manual
                                                 operator paths via this
                                                 CRUD use 'human:<username>'
                                                 or other prefix-matched
                                                 values.

    The slot-0072 ``LINK_STATE_VALUES`` import convention used
    ``# noqa: F401`` (side-effect-only import asserting vocabulary home).
    Slot 0073 upgraded that convention per #1085 finding #2; slot 0079
    inherits the upgrade: both ``CANONICAL_EVENT_LIFECYCLE_PHASES`` and
    ``DECIDED_BY_PREFIXES`` are imported and USED in real-guard
    ``ValueError``-raising validation.  The side-effect-only convention
    does not survive into slot 0079.

L33 dedicated CRUD module restriction:

    All MANUAL write paths to canonical_event_phase_log MUST go through
    this module's ``append_phase_transition()`` function.  There is NO
    direct-SQL escape hatch in the public API; future call sites adding
    ad-hoc INSERT SQL bypass the validation layer (Pattern 73 SSOT
    vocabulary checks + changed_by length bound + changed_by prefix
    discipline) and represent a Pattern 73 violation.  S81 grep audits
    sweep for direct INSERT into canonical_event_phase_log outside this
    module + the slot-0079 migration trigger function.

Reference:
    - ``docs/foundation/ARCHITECTURE_DECISIONS.md`` ADR-118 V2.40 Item 3 +
      V2.43 Item 2
    - ``src/precog/database/alembic/versions/0079_canonical_event_phase_log.py``
    - ``src/precog/database/crud_canonical_match_log.py`` (style + pattern
      reference; slot 0073 sister module)
    - ``src/precog/database/constants.py`` ``CANONICAL_EVENT_LIFECYCLE_PHASES``
      + ``DECIDED_BY_PREFIXES``
    - ``memory/build_spec_0079_pm_memo.md`` (binding build spec)
    - ``memory/s82_slot_0079_skip_memo.md`` (S82 SKIP verdict)
"""

import logging
from typing import Any, cast

from .connection import fetch_all, get_cursor
from .constants import CANONICAL_EVENT_LIFECYCLE_PHASES, DECIDED_BY_PREFIXES

logger = logging.getLogger(__name__)


# Maximum allowed length for ``changed_by`` matches the DDL column boundary
# (``VARCHAR(64)``).  Centralizing the constant here lets callers reference
# it without re-deriving the magic number; surfaced to module scope rather
# than duplicated inside the validation function.  Mirrors slot 0073's
# ``_DECIDED_BY_MAX_LENGTH`` shape.
_CHANGED_BY_MAX_LENGTH = 64


# =============================================================================
# CANONICAL EVENT PHASE LOG -- APPEND-ONLY WRITE PATH
# =============================================================================


def append_phase_transition(
    *,
    canonical_event_id: int,
    new_phase: str,
    changed_by: str,
    previous_phase: str | None = None,
    note: str | None = None,
) -> int:
    """Append one row to canonical_event_phase_log.  THIS IS THE ONLY SANCTIONED MANUAL WRITE PATH.

    Use case: operator-initiated phase corrections that bypass the normal
    canonical_events UPDATE path (e.g., correcting a misclassified phase
    in the audit stream without changing canonical_events.lifecycle_phase
    itself).  System-driven transitions land via the
    ``trg_canonical_events_log_phase_transition`` trigger and do NOT call
    this function.

    The function performs CRUD-layer validation that complements the DDL
    CHECK constraints (Pattern 73 SSOT real-guard discipline inherited
    from slot 0073):

        - ``new_phase`` MUST be in ``CANONICAL_EVENT_LIFECYCLE_PHASES``
          (Pattern 73 SSOT real-guard validation; raises ``ValueError``
          before SQL).
        - ``previous_phase`` MUST be NULL OR in
          ``CANONICAL_EVENT_LIFECYCLE_PHASES`` (Pattern 73 SSOT).
        - ``changed_by`` MUST start with one of ``DECIDED_BY_PREFIXES``
          (Pattern 73 SSOT real-guard validation).
        - ``len(changed_by)`` MUST be ``<= 64`` (boundary validation per
          slot-0073 #1085 finding #3 inheritance -- surfaces a clear
          ``ValueError`` before psycopg2 raises a generic
          StringDataRightTruncation).
        - ``canonical_event_id`` is passed through unchanged; psycopg2
          surfaces FK violations as ``ForeignKeyViolation``.

    Args:
        canonical_event_id: BIGINT FK into ``canonical_events.id``.  NOT
            NULL.  Validated as int at the type level; FK integrity
            surfaced at the SQL layer.
        new_phase: VARCHAR(32) NOT NULL.  MUST be in
            ``CANONICAL_EVENT_LIFECYCLE_PHASES``.  Always populated; even
            a "correction" audit row has a destination phase.
        changed_by: VARCHAR(64) NOT NULL actor attribution.  MUST start
            with one of ``DECIDED_BY_PREFIXES`` (``human:`` / ``service:``
            / ``system:``); MUST be <= 64 chars.  Operator-driven calls
            typically use ``'human:<username>'``; service-driven calls
            use ``'service:<svc-name>'``.  The trigger emits
            ``'system:trigger'`` and does NOT call this function.
        previous_phase: VARCHAR(32) NULL.  When non-NULL, MUST be in
            ``CANONICAL_EVENT_LIFECYCLE_PHASES``.  NULL allowed for
            corrections that record a fresh-state transition (no
            predecessor in the operator's framing).
        note: Free-text TEXT operator-readable explanation.  NULL
            acceptable; no boundary enforcement (TEXT is unbounded).

    Returns:
        The BIGSERIAL ``id`` of the newly-inserted log row.

    Raises:
        ValueError: validation failure (new_phase / previous_phase /
            changed_by domain or boundary errors) -- surfaced before SQL.
        psycopg2.errors.ForeignKeyViolation: canonical_event_id references
            a non-existent canonical_events row.
        psycopg2.errors.CheckViolation: should not occur in practice
            (CRUD validation precedes DDL CHECK), but surfaces if the DDL
            CHECK and the Python constant drift apart (Pattern 73 SSOT
            failure mode -- the dedicated SSOT parity test catches this
            shape pre-merge).

    Example:
        >>> log_id = append_phase_transition(
        ...     canonical_event_id=42,
        ...     new_phase="live",
        ...     changed_by="human:eric",
        ...     previous_phase="pre_event",
        ...     note="Manual correction: missed the actual kickoff time",
        ... )

    Educational Note:
        Most phase-log rows arrive via the trigger, not this function.
        Operators reading the audit stream should expect ~99% of rows
        to carry ``changed_by='system:trigger'``; rows with ``human:``
        or ``service:`` prefixes are operator-driven corrections that
        warrant runbook attention (someone manually augmented the audit
        stream).  The note column captures the operator's reasoning.

    Reference:
        - Migration 0079 (table DDL + CHECK constraints + trigger)
        - ``constants.py`` ``CANONICAL_EVENT_LIFECYCLE_PHASES`` +
          ``DECIDED_BY_PREFIXES``
        - Build spec § 4 (CRUD API surface specification)
        - Slot 0073 ``crud_canonical_match_log.append_match_log_row()``
          (sister-module style + validation reference)
    """
    # Validate BEFORE opening the cursor so callers see a clear validation
    # message rather than a CheckViolation from psycopg2.  Slot 0073
    # inheritance: same shape as ``_validate_append_match_log_args``.
    _validate_append_phase_transition_args(
        new_phase=new_phase,
        previous_phase=previous_phase,
        changed_by=changed_by,
    )

    with get_cursor(commit=True) as cur:
        # ---- The append (single INSERT, RETURNING id) -----------------------
        # No UPDATE / DELETE / UPSERT -- this is the ONLY sanctioned manual
        # write path.  No transaction-spanning two-table-write here either,
        # because the trigger-driven write path handles canonical_events
        # transitions atomically; this function is for AUDIT-ONLY corrections.
        cur.execute(
            """
            INSERT INTO canonical_event_phase_log (
                canonical_event_id, previous_phase, new_phase, changed_by, note
            ) VALUES (
                %s, %s, %s, %s, %s
            )
            RETURNING id
            """,
            (
                canonical_event_id,
                previous_phase,
                new_phase,
                changed_by,
                note,
            ),
        )
        row = cur.fetchone()
        return cast("int", row["id"])


def _validate_append_phase_transition_args(
    *,
    new_phase: str,
    previous_phase: str | None,
    changed_by: str,
) -> None:
    """Pattern 73 SSOT + boundary validation for phase-transition append args.

    Centralizing the validation here keeps ``append_phase_transition``'s
    "no SQL on validation failure" contract intact (callers asserting
    ``mock_get_cursor.assert_not_called()`` still pass).  Mirrors slot
    0073's ``_validate_append_match_log_args`` shape.
    """
    # new_phase must be in the canonical 8-value vocabulary.  Pattern 73 SSOT.
    if new_phase not in CANONICAL_EVENT_LIFECYCLE_PHASES:
        raise ValueError(
            f"new_phase {new_phase!r} not in canonical "
            f"CANONICAL_EVENT_LIFECYCLE_PHASES {CANONICAL_EVENT_LIFECYCLE_PHASES!r}; "
            "pattern 73 SSOT vocabulary violation"
        )

    # previous_phase: nullable, but if non-NULL must be in the same vocabulary.
    if previous_phase is not None and previous_phase not in CANONICAL_EVENT_LIFECYCLE_PHASES:
        raise ValueError(
            f"previous_phase {previous_phase!r} not in canonical "
            f"CANONICAL_EVENT_LIFECYCLE_PHASES {CANONICAL_EVENT_LIFECYCLE_PHASES!r}; "
            "pattern 73 SSOT vocabulary violation"
        )

    # changed_by prefix discipline: must start with one of the canonical
    # actor-taxonomy prefixes from constants.py:DECIDED_BY_PREFIXES.  CHECK
    # cannot enforce string format, so this is the discipline.  Slot 0073
    # inheritance.
    if not any(changed_by.startswith(p) for p in DECIDED_BY_PREFIXES):
        raise ValueError(
            f"changed_by {changed_by!r} must start with one of "
            f"DECIDED_BY_PREFIXES {DECIDED_BY_PREFIXES!r}; "
            "pattern 73 SSOT vocabulary violation"
        )

    # changed_by length boundary per slot-0073 #1085 finding #3 inheritance.
    if len(changed_by) > _CHANGED_BY_MAX_LENGTH:
        raise ValueError(
            f"changed_by length {len(changed_by)} exceeds "
            f"VARCHAR({_CHANGED_BY_MAX_LENGTH}) column boundary; got {changed_by!r}"
        )


# =============================================================================
# CANONICAL EVENT PHASE LOG -- READ OPERATIONS
# =============================================================================


def get_phase_history_for_event(
    canonical_event_id: int,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Get the phase-transition history for a canonical event, newest-first.

    The operator audit hot path: when an operator asks "what's the phase
    history for this event?", they call this function.  Returns rows in
    descending ``transition_at`` order (most-recent first); the underlying
    ``idx_canonical_event_phase_log_event_transition`` composite index
    serves both the WHERE filter and the ORDER BY in one scan, keeping
    this O(log n) + limit-bounded regardless of total log-table size.

    Args:
        canonical_event_id: BIGINT target into the ``canonical_events.id``
            primary key.
        limit: Maximum rows returned.  Defaults to 50 -- large enough for
            most operator runbook queries, small enough to bound the
            per-query overhead.  Pagination beyond 50 rows is not
            currently supported (file an issue if a use case justifies it).

    Returns:
        List of full row dicts (possibly empty), ordered by
        ``transition_at DESC``.  Keys: id, canonical_event_id,
        previous_phase, new_phase, transition_at, changed_by, note,
        created_at.

    Example:
        >>> history = get_phase_history_for_event(42)
        >>> for row in history:
        ...     print(f"{row['transition_at']}: "
        ...           f"{row['previous_phase']}->{row['new_phase']} "
        ...           f"by {row['changed_by']}")

    Reference:
        - Migration 0079 (idx_canonical_event_phase_log_event_transition)
    """
    query = """
        SELECT id, canonical_event_id, previous_phase, new_phase,
               transition_at, changed_by, note, created_at
        FROM canonical_event_phase_log
        WHERE canonical_event_id = %s
        ORDER BY transition_at DESC
        LIMIT %s
    """
    return fetch_all(query, (canonical_event_id, limit))


# =============================================================================
# Sentinel: CANONICAL_EVENT_LIFECYCLE_PHASES + DECIDED_BY_PREFIXES are imported
# and USED above in real-guard ``ValueError``-raising validation
# (_validate_append_phase_transition_args).  If a future refactor drops the
# validation, the imports become unused and ruff (F401) will fire -- closing
# the side-effect-only-import drift surface that #1085 finding #2 strengthening
# prevents (slot 0073 inheritance).
# =============================================================================
