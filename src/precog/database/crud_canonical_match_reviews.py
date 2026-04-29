"""CRUD operations for canonical_match_reviews — operator review state machine.

Cohort 3 final slot of the canonical-layer foundation (ADR-118 v2.41
amendment + v2.42 sub-amendment B + session-78 Cohort 3 design council +
session-80 S82 design-stage P41 council outcomes inherited from slot 0072
+ session-81 slot-0073 conventions + session-82 PM-composed build spec at
``memory/build_spec_0074_pm_memo.md`` (Holden re-engagement
GO-WITH-NOTES; all 4 amendments applied)).  Sister module to
``crud_canonical_match_log.py`` (slot 0073) and
``crud_canonical_match_overrides.py`` (slot 0074, sibling); uses the same
raw-psycopg2 + ``get_cursor`` / ``fetch_one`` / ``fetch_all`` +
RealDictCursor + heavy-docstring conventions.

Tables covered:
    - ``canonical_match_reviews`` (Migration 0074) — operational-state
      table tracking operator review of canonical_market_links rows.
      Reviews die with their link (ON DELETE CASCADE on link_id);
      audit trail of state transitions is preserved on
      ``canonical_match_log`` via the slot-0073 SET NULL audit-survival
      semantics.

OPERATIONAL CRUD SURFACE:

    Unlike ``crud_canonical_match_log`` (which exposes exactly ONE
    sanctioned write path because the audit ledger is append-only),
    ``crud_canonical_match_reviews`` exposes the full create / read /
    transition CRUD surface that the operator review state machine needs:

        - ``create_review()`` — create a 'pending' review row for a link.
        - ``transition_review()`` — UPDATE the review_state with state-
          machine validation; writes a canonical_match_log row for
          'review_approve' / 'review_reject' transitions (NOT for
          'pending' / 'needs_info' transitions).
        - ``get_review()`` — read by id.
        - ``get_reviews_for_link()`` — all reviews for a given link.
        - ``get_pending_reviews()`` — operator alert query (uses partial
          index on ``review_state = 'pending'``).

    There is NO ``delete_review()`` API: deletion happens implicitly via
    the link's CASCADE.  Operators do not delete reviews directly; they
    transition them through the state machine to a terminal state.

State-machine semantics (build spec § 4a):

    Allowed forward transitions:
        'pending'    -> {'approved', 'rejected', 'needs_info'}
        'needs_info' -> {'approved', 'rejected', 'pending'}      -- can re-pend
        'approved'   -> {'rejected', 'needs_info'}                -- can revisit
        'rejected'   -> {'approved', 'needs_info'}                -- can revisit

    Self-transitions raise ValueError REGARDLESS of source state.  Per
    Holden re-engagement Item 3 (P2): the self-transition rule beats the
    matrix when they appear to conflict; the matrix lists what IS allowed
    forward, the rule excludes the diagonal.  All of these raise:

        'pending'    -> 'pending'
        'approved'   -> 'approved'
        'rejected'   -> 'rejected'
        'needs_info' -> 'needs_info'

Pattern 73 SSOT discipline (CLAUDE.md Critical Pattern #8):

    Two vocabularies are SSOT-anchored at
    ``src/precog/database/constants.py``:

        ``REVIEW_STATE_VALUES``   — 4-value ``review_state`` discriminator
                                    (pending / approved / rejected /
                                    needs_info).  Inline DDL CHECK on
                                    canonical_match_reviews.review_state
                                    cites this constant by name; this
                                    module uses it in REAL-GUARD
                                    validation — ``if new_state not in
                                    REVIEW_STATE_VALUES: raise
                                    ValueError(...)``.

        ``DECIDED_BY_PREFIXES``   — 3-prefix actor taxonomy
                                    (``human:`` / ``service:`` /
                                    ``system:``).  Reviewers may be
                                    human (operators) or service
                                    (Cohort 5+ automated review services).
                                    CHECK constraint cannot enforce
                                    free-text format; this module's real-
                                    guard validation in
                                    ``transition_review()`` is the
                                    discipline.

    Both constants are imported and USED in real-guard ValueError-raising
    validation, NOT side-effect-only ``# noqa: F401`` imports.  The
    slot-0072 side-effect-only convention does not survive into slot 0074
    (per #1085 finding #2 strengthening + slot-0073 precedent).

manual_v1-on-human-decided-actions convention (scope-extended from slot
0073, build spec § 5c):

    The 7-value canonical_match_log.action vocabulary partitions into:
      - Algorithm-decided: 'link', 'unlink', 'relink', 'quarantine'
        (Cohort 5+ matcher writes; algorithm_id reflects the deciding
        algorithm)
      - Human-decided: 'override', 'review_approve', 'review_reject'
        (slot 0074+ CRUD writes; algorithm_id = manual_v1.id by
        convention)

    For human-decided actions, ``algorithm_id=manual_v1.id`` is a
    CATEGORY-FIT PLACEHOLDER, not a fact:
      - Overrides + review state transitions are decided by humans
        (``decided_by='human:<username>'``).
      - ``algorithm_id`` is NOT NULL on canonical_match_log; we use the
        ``manual_v1`` placeholder so future-log-readers can still JOIN
        to ``match_algorithm`` for the category metadata ("this row was
        a human decision").
      - Future log-readers MUST NOT mistake ``algorithm_id=manual_v1.id``
        on these action rows for "the manual_v1 algorithm decided this."
        The ``decided_by`` column carries the actual actor identity.

    This convention is enforced by this module (which resolves
    ``manual_v1.id`` via lookup at module load + passes it explicitly to
    ``append_match_log_row()``); the schema itself does not constrain it
    (cannot — algorithm_id NOT NULL is a schema invariant; "must equal
    manual_v1.id when action='review_approve' / 'review_reject'" is
    policy-level).

L33 dedicated CRUD module restriction:

    All review state transitions MUST go through this module's
    ``transition_review()`` function.  There is NO direct-SQL escape
    hatch in the public API; future call sites adding ad-hoc UPDATE SQL
    bypass the validation layer (Pattern 73 SSOT vocabulary checks +
    state-transition matrix + audit-log-write coupling) and represent a
    Pattern 73 violation.  S81 grep audits sweep for direct UPDATE on
    canonical_match_reviews outside this module.

Reference:
    - ``docs/foundation/ARCHITECTURE_DECISIONS.md`` ADR-118 v2.41 +
      v2.42 sub-amendment B
    - ``src/precog/database/alembic/versions/0074_canonical_match_overrides_reviews.py``
    - ``src/precog/database/crud_canonical_match_log.py`` (sister module
      + style reference; the audit-log sink for review transitions)
    - ``src/precog/database/constants.py`` ``REVIEW_STATE_VALUES`` +
      ``DECIDED_BY_PREFIXES``
    - ``memory/build_spec_0074_pm_memo.md`` (binding build spec)
    - ``memory/holden_reengagement_0074_memo.md`` (Holden re-engagement
      verdict + amendments)
"""

import logging
from datetime import UTC, datetime
from typing import Any, cast

from .connection import fetch_all, fetch_one, get_cursor
from .constants import DECIDED_BY_PREFIXES, REVIEW_STATE_VALUES
from .crud_canonical_match_log import (
    _append_match_log_row_in_cursor,
    get_manual_v1_algorithm_id,
)

logger = logging.getLogger(__name__)


# Maximum allowed length for ``reviewer`` matches the DDL column boundary
# (``VARCHAR(64)``).  Surfacing the constant at module scope mirrors slot
# 0073's ``_DECIDED_BY_MAX_LENGTH`` convention.
_REVIEWER_MAX_LENGTH = 64

# Maximum allowed length for ``flagged_reason`` matches the DDL column
# boundary (``VARCHAR(256)``).  Per #1085 finding #3 inheritance — surface
# clear ValueError at the CRUD layer rather than psycopg2's generic
# StringDataRightTruncation.
_FLAGGED_REASON_MAX_LENGTH = 256


# State-machine forward-transition matrix.  Self-transitions are NOT in
# the per-source frozensets — the ``_validate_transition`` helper rejects
# them as a separate guard before consulting the matrix (per Holden
# re-engagement Item 3 P2: self-transition rule beats the matrix on the
# diagonal).
_REVIEW_STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"approved", "rejected", "needs_info"}),
    "needs_info": frozenset({"approved", "rejected", "pending"}),
    "approved": frozenset({"rejected", "needs_info"}),
    "rejected": frozenset({"approved", "needs_info"}),
}

# canonical_match_log action mapping for review transitions.  Only
# 'approved' / 'rejected' transitions write a log row; 'pending' /
# 'needs_info' are intermediate and NOT audit-ledger events.
_TRANSITION_LOG_ACTION: dict[str, str] = {
    "approved": "review_approve",
    "rejected": "review_reject",
}


def _validate_transition(current_state: str, new_state: str) -> None:
    """Validate that current_state -> new_state is allowed.

    Raises ValueError if:
        - ``current_state == new_state`` (self-transition; rule beats
          the matrix per Holden Item 3 P2).
        - ``new_state not in _REVIEW_STATE_TRANSITIONS[current_state]``
          (matrix violation; e.g., 'approved' -> 'pending' is not allowed
          by design).

    Self-transitions are checked FIRST because they would otherwise be
    caught by the matrix lookup in some-but-not-all cases (e.g.,
    'pending' -> 'pending' is not in the 'pending' transitions set, so
    the matrix would also reject it; but 'approved' -> 'approved' is
    handled cleanly by the explicit guard regardless of how the matrix
    is structured).
    """
    if current_state == new_state:
        raise ValueError(
            f"self-transition {current_state!r} -> {new_state!r} not "
            f"allowed; the self-transition rule beats the state-machine "
            f"matrix on the diagonal regardless of source state"
        )
    allowed = _REVIEW_STATE_TRANSITIONS.get(current_state, frozenset())
    if new_state not in allowed:
        raise ValueError(
            f"state transition {current_state!r} -> {new_state!r} not "
            f"allowed; valid forward transitions from {current_state!r} "
            f"are {sorted(allowed)!r}"
        )


# =============================================================================
# canonical_match_reviews — CREATE
# =============================================================================


def create_review(
    *,
    link_id: int,
    flagged_reason: str | None = None,
) -> int:
    """Create a 'pending' review row for a link.  Returns the review id.

    Per build spec § 4a: review creation is NOT in the audit ledger's
    action vocabulary.  Only the state TRANSITIONS (approve/reject)
    write to the log.  Created reviews start in 'pending'; the log
    entry pairs with the eventual transition.

    Validation:
        - ``link_id`` must be a valid ``canonical_market_links.id``;
          psycopg2 surfaces FK violation as ``ForeignKeyViolation``.
        - ``flagged_reason`` (if provided) must be ``<= 256`` chars per
          #1085 finding #3 inheritance (boundary validation at the CRUD
          layer rather than letting psycopg2 raise a generic
          StringDataRightTruncation when VARCHAR(256) overflows).

    Args:
        link_id: BIGSERIAL FK into ``canonical_market_links.id``.
        flagged_reason: Optional structured short-form reason for the
            review (e.g., "low confidence + ambiguous domain").  TEXT-
            field-style free text but bounded to VARCHAR(256) at the
            DDL layer.

    Returns:
        The BIGSERIAL ``id`` of the newly-created review row.

    Raises:
        ValueError: ``flagged_reason`` exceeds 256 chars.
        psycopg2.errors.ForeignKeyViolation: ``link_id`` references a
            non-existent row.
    """
    if flagged_reason is not None and len(flagged_reason) > _FLAGGED_REASON_MAX_LENGTH:
        raise ValueError(
            f"flagged_reason length {len(flagged_reason)} exceeds "
            f"VARCHAR({_FLAGGED_REASON_MAX_LENGTH}) column boundary; got "
            f"{flagged_reason!r}"
        )

    query = """
        INSERT INTO canonical_match_reviews (
            link_id, review_state, flagged_reason
        ) VALUES (
            %s, 'pending', %s
        )
        RETURNING id
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query, (link_id, flagged_reason))
        row = cur.fetchone()
    return cast("int", row["id"])


# =============================================================================
# canonical_match_reviews — STATE TRANSITION
# =============================================================================


def transition_review(
    *,
    review_id: int,
    new_state: str,
    reviewer: str,
    reviewed_at: datetime | None = None,
) -> None:
    """Transition a review's state.

    Writes a ``canonical_match_log`` row for ``approved`` / ``rejected``
    transitions (action='review_approve' / 'review_reject') via the
    manual_v1-on-human-decided-actions convention.  Does NOT write a log
    row for ``pending`` / ``needs_info`` transitions (only resolved
    decisions are audit-ledger events).

    Atomic single-cursor write per Glokta F1 + F5 (slot 0074 review): the
    SELECT (review state + link attribution via JOIN), the UPDATE on
    canonical_match_reviews, and (for resolved transitions) the
    canonical_match_log INSERT all execute on the SAME transaction —
    closes the prior TOCTOU window where a concurrent link DELETE between
    the review-state read and the log-attribution lookup would have
    surfaced as silent NULL platform_market_id.

    Validation:
        - ``new_state`` MUST be in ``REVIEW_STATE_VALUES`` (Pattern 73
          SSOT real-guard validation; raises ``ValueError`` before SQL).
        - ``reviewer`` MUST start with one of ``DECIDED_BY_PREFIXES``
          (Pattern 73 SSOT real-guard validation).
        - ``len(reviewer)`` MUST be ``<= 64`` (boundary validation per
          #1085 finding #3 inheritance).
        - ``current_state -> new_state`` MUST be an allowed transition
          per ``_REVIEW_STATE_TRANSITIONS`` (state-machine matrix).
        - Self-transitions (``current_state == new_state``) raise
          ValueError REGARDLESS of source state (per Holden re-engagement
          Item 3 P2: self-transition rule beats the matrix on the
          diagonal).

    Side-effects (atomic — same transaction):
        - SELECT review state + link attribution (via JOIN to
          canonical_market_links).
        - UPDATE canonical_match_reviews SET review_state, reviewer,
          reviewed_at WHERE id = review_id.
        - For 'approved' / 'rejected' transitions: INSERT
          canonical_match_log row with action='review_approve' /
          'review_reject', link_id=review.link_id, decided_by=reviewer,
          algorithm_id=manual_v1.id (the convention placeholder),
          decided_at=reviewed_at.

    Args:
        review_id: BIGSERIAL ``canonical_match_reviews.id`` to transition.
        new_state: Target state; MUST be in REVIEW_STATE_VALUES.
        reviewer: Actor attribution; MUST start with one of
            DECIDED_BY_PREFIXES; MUST be <= 64 chars.
        reviewed_at: Optional explicit timestamp for the transition;
            defaults to ``datetime.now(UTC)`` if None.

    Raises:
        ValueError: validation failure (state vocabulary, prefix,
            length, transition matrix, self-transition rule).
        LookupError: ``review_id`` does not exist (review_id is not a
            FK; we surface a typed lookup error before SQL UPDATE
            silently affects 0 rows).
        RuntimeError: ``manual_v1`` algorithm seed missing (Migration
            0071 not applied).

    Example:
        >>> review_id = create_review(link_id=42)
        >>> transition_review(
        ...     review_id=review_id,
        ...     new_state="approved",
        ...     reviewer="human:eric",
        ... )
        # UPDATE + canonical_match_log INSERT (action='review_approve')
        # both committed atomically.
    """
    # ---- Pattern 73 SSOT real-guard validation -------------------------------
    if new_state not in REVIEW_STATE_VALUES:
        raise ValueError(
            f"new_state {new_state!r} not in canonical REVIEW_STATE_VALUES "
            f"{REVIEW_STATE_VALUES!r}; pattern 73 SSOT vocabulary violation"
        )

    # reviewer prefix discipline.
    if not any(reviewer.startswith(p) for p in DECIDED_BY_PREFIXES):
        raise ValueError(
            f"reviewer {reviewer!r} must start with one of "
            f"DECIDED_BY_PREFIXES {DECIDED_BY_PREFIXES!r}; "
            "pattern 73 SSOT vocabulary violation"
        )

    # reviewer length boundary per #1085 finding #3.
    if len(reviewer) > _REVIEWER_MAX_LENGTH:
        raise ValueError(
            f"reviewer length {len(reviewer)} exceeds "
            f"VARCHAR({_REVIEWER_MAX_LENGTH}) column boundary; got "
            f"{reviewer!r}"
        )

    if reviewed_at is None:
        reviewed_at = datetime.now(UTC)

    log_action = _TRANSITION_LOG_ACTION.get(new_state)

    # ---- Atomic SELECT + UPDATE + optional log INSERT -----------------------
    # All statements share a single cursor / transaction per Glokta F5
    # (slot 0074 review): the JOIN pulls review_state alongside the
    # link's (canonical_market_id, platform_market_id) so the audit-row
    # attribution is not read in a separate transaction (which would
    # admit a TOCTOU window for concurrent CASCADE on link deletion
    # between the UPDATE commit and the link lookup).
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            SELECT cmr.review_state,
                   cmr.link_id,
                   cml.canonical_market_id AS link_canonical_market_id,
                   cml.platform_market_id  AS link_platform_market_id
            FROM canonical_match_reviews cmr
            LEFT JOIN canonical_market_links cml ON cml.id = cmr.link_id
            WHERE cmr.id = %s
            """,
            (review_id,),
        )
        current_row = cur.fetchone()
        if current_row is None:
            raise LookupError(f"review_id {review_id} does not exist in canonical_match_reviews")
        current_state = cast("str", current_row["review_state"])
        link_id = cast("int", current_row["link_id"])

        # State-transition matrix + self-transition rule (Holden Item 3 P2).
        _validate_transition(current_state, new_state)

        cur.execute(
            """
            UPDATE canonical_match_reviews
            SET review_state = %s,
                reviewer = %s,
                reviewed_at = %s
            WHERE id = %s
            """,
            (new_state, reviewer, reviewed_at, review_id),
        )

        # Audit-ledger write for resolved decisions only.  'pending' /
        # 'needs_info' transitions are intermediate and NOT audit events
        # (per build spec § 4a).
        if log_action is not None:
            canonical_market_id = cast("int | None", current_row["link_canonical_market_id"])
            platform_market_id = cast("int | None", current_row["link_platform_market_id"])

            if platform_market_id is None:
                # Unreachable in practice: link_id is NOT NULL FK on
                # canonical_match_reviews, the LEFT JOIN matches on the
                # link's id, and canonical_market_links.platform_market_id
                # is NOT NULL.  The only way to reach this is if the link
                # row was deleted between the SELECT JOIN and... wait, the
                # SELECT JOIN already happened.  This guard remains as a
                # type-narrowing aid for mypy + surfaces an explicit error
                # if the schema invariant ever changes.
                raise RuntimeError(
                    f"link_id {link_id} has NULL platform_market_id; "
                    "canonical_match_log requires NOT NULL — schema "
                    "invariant violated"
                )

            # Resolve manual_v1.id ONLY after validation passes (CI-failure
            # fix: previously resolved before the cursor block, which forced
            # the helper's get_cursor() call to fire BEFORE self-transition /
            # matrix / LookupError validation could short-circuit.  Mocked
            # unit tests for self_transition_approved/rejected and
            # missing-review-id failed in fresh CI workers where the
            # _MANUAL_V1_ID_CACHE was unpopulated; locally the cache was
            # populated by a prior test in the same process.  Moving the
            # resolution inside the post-validation branch ensures unit tests
            # patching `get_cursor` at the reviews-module level can short-
            # circuit the entire path before any DB call is attempted.
            # The helper opens its own cursor only on the first call per
            # process; subsequent calls return the cached id with zero DB
            # cost — nesting is bounded to first call.)
            algorithm_id = get_manual_v1_algorithm_id()
            _append_match_log_row_in_cursor(
                cur,
                link_id=link_id,
                platform_market_id=platform_market_id,
                canonical_market_id=canonical_market_id,
                action=log_action,
                confidence=None,  # human review has no algorithmic confidence
                algorithm_id=algorithm_id,  # manual_v1.id placeholder
                features=None,
                prior_link_id=None,
                decided_by=reviewer,
                note=f"review {new_state}",
            )


# =============================================================================
# canonical_match_reviews — READ OPERATIONS
# =============================================================================


def get_review(review_id: int) -> dict[str, Any] | None:
    """Read a single review row by id.  Returns None if not found."""
    query = """
        SELECT id, link_id, review_state, reviewer, reviewed_at,
               flagged_reason, created_at
        FROM canonical_match_reviews
        WHERE id = %s
    """
    return fetch_one(query, (review_id,))


def get_reviews_for_link(link_id: int) -> list[dict[str, Any]]:
    """All reviews for a given link, ordered by created_at DESC.

    Operator query: "show me the review history for this link".  Uses the
    ``idx_canonical_match_reviews_link_id`` FK-target index.
    """
    query = """
        SELECT id, link_id, review_state, reviewer, reviewed_at,
               flagged_reason, created_at
        FROM canonical_match_reviews
        WHERE link_id = %s
        ORDER BY created_at DESC
    """
    return fetch_all(query, (link_id,))


def get_pending_reviews(limit: int = 100) -> list[dict[str, Any]]:
    """Operator alert query — uses partial index on review_state='pending'.

    Hot path for the review-queue dashboard.  Returns rows in
    created_at-ascending order so the OLDEST pending reviews surface
    first (operators address the backlog FIFO).

    Args:
        limit: Maximum rows returned.  Defaults to 100; large enough to
            populate a single dashboard page, small enough to bound the
            per-query overhead.

    Returns:
        List of full review row dicts (possibly empty).
    """
    query = """
        SELECT id, link_id, review_state, reviewer, reviewed_at,
               flagged_reason, created_at
        FROM canonical_match_reviews
        WHERE review_state = 'pending'
        ORDER BY created_at ASC
        LIMIT %s
    """
    return fetch_all(query, (limit,))


# =============================================================================
# Sentinel: REVIEW_STATE_VALUES + DECIDED_BY_PREFIXES are imported and USED
# above in real-guard ``ValueError``-raising validation (transition_review).
# If a future refactor drops the validation, the imports become unused and
# ruff (F401) will fire — closing the side-effect-only-import drift surface
# that #1085 finding #2 strengthening prevents.  This is the canonical
# strengthening of slot-0072's LINK_STATE_VALUES side-effect-only-import
# convention (which used a noqa F401 comment to keep the import alive purely
# for vocabulary-home assertion).
# =============================================================================
