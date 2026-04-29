"""CRUD operations for canonical_match_overrides — operator override surface.

Cohort 3 final slot of the canonical-layer foundation (ADR-118 v2.41
amendment + v2.42 sub-amendment B + session-78 Cohort 3 design council +
session-80 S82 design-stage P41 council outcomes inherited from slot 0072
+ session-81 slot-0073 conventions + session-82 PM-composed build spec at
``memory/build_spec_0074_pm_memo.md`` (Holden re-engagement
GO-WITH-NOTES; all 4 amendments applied)).  Sister module to
``crud_canonical_match_log.py`` (slot 0073) and
``crud_canonical_match_reviews.py`` (slot 0074, sibling); uses the same
raw-psycopg2 + ``get_cursor`` / ``fetch_one`` / ``fetch_all`` +
RealDictCursor + heavy-docstring conventions.

Tables covered:
    - ``canonical_match_overrides`` (Migration 0074) — operator
      assertion table.  An override row says "the matcher MUST emit
      (or MUST NOT emit) an active link for this platform_market"; it
      is the human-decided override of the algorithmic matching layer.
      Lifecycle is INSERT → DELETE (no in-place mutation); replacement
      = DELETE-then-INSERT, with both operations writing audit rows
      to ``canonical_match_log``.

OPERATIONAL CRUD SURFACE:

    Unlike ``crud_canonical_match_log`` (which exposes exactly ONE
    sanctioned write path because the audit ledger is append-only),
    ``crud_canonical_match_overrides`` exposes the full create / delete /
    read CRUD surface that the override workflow needs:

        - ``create_override()`` — INSERT a new override row + write a
          canonical_match_log row with action='override' (atomic).
        - ``delete_override()`` — DELETE the override row + write a
          canonical_match_log row with action='override' (note column
          carries "deleted: <reason>" prefix to distinguish from create).
        - ``get_override()`` — read by id.
        - ``get_override_for_platform_market()`` — UNIQUE-constraint-
          backed lookup (at most one override per platform_market_id).
        - ``get_overrides_by_polarity()`` — alert-query hot path
          (partial index on canonical_market_id + non-partial index on
          polarity).

    There is NO ``update_override()`` API: replacement = DELETE + INSERT
    so each operation lands a distinct audit row.  In-place UPDATE would
    silently mutate the record without the audit trail showing both the
    old AND new states.

human-only invariant (build spec § 4b + Holden re-engagement Item 1 P1):

    Overrides are HUMAN-DECIDED BY DEFINITION.  The ``created_by`` and
    ``deleted_by`` parameters MUST start with ``'human:'`` prefix
    (``'service:'`` and ``'system:'`` are rejected at the CRUD boundary).

    This is a STRICTER rule than canonical_match_log's
    DECIDED_BY_PREFIXES (which allows the full 3-prefix taxonomy), and
    is enforced ONLY at the CRUD layer in this module.  The
    canonical_match_log row written by create_override / delete_override
    carries the same human-prefixed value through to its decided_by
    column, where the slot-0073 ``append_match_log_row()`` validation
    accepts it (human: is a member of DECIDED_BY_PREFIXES).

    A future test asserts that the convention is observable from the LOG
    side (per Holden Item 1 P1 bidirectional anchoring): the
    canonical_match_log row written for an override MUST have decided_by
    starting with 'human:'.

polarity-pairing rule (build spec § 4b):

    The polarity discriminator gates canonical_market_id NULL/NOT-NULL:

        polarity='MUST_MATCH'      ->  canonical_market_id IS NOT NULL
        polarity='MUST_NOT_MATCH'  ->  canonical_market_id IS NULL

    The CRUD-layer validation in ``create_override()`` raises ValueError
    BEFORE INSERT when the pairing is violated; the DDL CHECK
    (``ck_canonical_match_overrides_polarity_pairing``) is defense-in-
    depth (catches direct-SQL bypass).  Tests MUST exercise BOTH
    branches (MUST_MATCH with NULL → reject; MUST_NOT_MATCH with non-
    NULL → reject) plus the happy paths.

Pattern 73 SSOT discipline (CLAUDE.md Critical Pattern #8):

    Two vocabularies are SSOT-anchored at
    ``src/precog/database/constants.py``:

        ``POLARITY_VALUES``       — 2-value polarity vocabulary
                                    (MUST_MATCH / MUST_NOT_MATCH).  Pre-
                                    positioned in slot 0072; finally
                                    USED in real-guard validation here.
                                    Inline DDL CHECK on
                                    canonical_match_overrides.polarity
                                    cites this constant by name.

        ``DECIDED_BY_PREFIXES``   — 3-prefix actor taxonomy (``human:`` /
                                    ``service:`` / ``system:``).  THIS
                                    module restricts to the ``human:``
                                    prefix only (overrides are human-
                                    decided by definition); the broader
                                    taxonomy is what canonical_match_log
                                    accepts via the slot-0073 module.

    Both constants are imported and USED in real-guard ValueError-raising
    validation, NOT side-effect-only ``# noqa: F401`` imports.

manual_v1-on-human-decided-actions convention (scope-extended from slot
0073, build spec § 5c):

    Every canonical_match_log row written by this module
    (create_override + delete_override) carries
    ``algorithm_id=manual_v1.id`` per the convention.  This is the
    CATEGORY-FIT PLACEHOLDER pattern: overrides are human-decided
    (decided_by='human:<username>' carries the actual actor identity);
    the algorithm_id column needs a NOT NULL value, and we use the
    manual_v1 seed row from Migration 0071.

    Future log-readers MUST NOT mistake ``algorithm_id=manual_v1.id`` on
    these action rows for "the manual_v1 algorithm decided this override."
    The decided_by column is the source-of-truth for actor identity.

L33 dedicated CRUD module restriction:

    All write paths to canonical_match_overrides MUST go through this
    module's ``create_override()`` and ``delete_override()`` functions.
    There is NO direct-SQL escape hatch in the public API; future call
    sites adding ad-hoc INSERT or DELETE SQL bypass the validation layer
    (Pattern 73 SSOT vocabulary checks + polarity-pairing rule + human-
    only invariant + audit-log-write coupling) and represent a
    Pattern 73 violation.  S81 grep audits sweep for direct INSERT /
    DELETE on canonical_match_overrides outside this module.

#1085 finding #17 inheritance (decided_by="human:" empty-username
permitted):

    The current real-guard validation accepts ``created_by="human:"``
    (empty username after the prefix).  This is CONSISTENT with the
    slot-0072 + slot-0073 prefix-only validation; tightening the rule
    to require ``len(created_by) > len("human:")`` is a Phase 5+
    consideration (the convention is "starts with one of the prefixes",
    not "starts with one of the prefixes + has a non-empty payload").
    Documented here so the eventual tightening lands intentionally
    rather than as a silent change.

Reference:
    - ``docs/foundation/ARCHITECTURE_DECISIONS.md`` ADR-118 v2.41 +
      v2.42 sub-amendment B
    - ``src/precog/database/alembic/versions/0074_canonical_match_overrides_reviews.py``
    - ``src/precog/database/crud_canonical_match_log.py`` (sister module
      + style reference; the audit-log sink for override events)
    - ``src/precog/database/constants.py`` ``POLARITY_VALUES`` +
      ``DECIDED_BY_PREFIXES``
    - ``memory/build_spec_0074_pm_memo.md`` (binding build spec)
    - ``memory/holden_reengagement_0074_memo.md`` (Holden re-engagement
      verdict + amendments)
"""

import logging
from typing import Any, cast

from .connection import fetch_all, fetch_one, get_cursor
from .constants import DECIDED_BY_PREFIXES, POLARITY_VALUES
from .crud_canonical_match_log import (
    _append_match_log_row_in_cursor,
    get_manual_v1_algorithm_id,
)

logger = logging.getLogger(__name__)


# Maximum allowed length for ``created_by`` / ``deleted_by`` matches the
# DDL column boundary (``VARCHAR(64)``).  Surface clear ValueError at
# CRUD layer rather than psycopg2's StringDataRightTruncation per #1085
# finding #3 inheritance.
_CREATED_BY_MAX_LENGTH = 64

# The human-only override invariant (Holden Item 1 P1): overrides are
# human-decided by definition, so the prefix is restricted to 'human:'
# even though canonical_match_log.decided_by accepts the broader
# DECIDED_BY_PREFIXES taxonomy.  Sentinel: ``DECIDED_BY_PREFIXES`` is
# imported below as a real-guard reference (assertion that 'human:' is
# IN the canonical taxonomy — keeps the import live + documents the
# narrowing from the wider set).
_HUMAN_ONLY_PREFIX = "human:"
assert _HUMAN_ONLY_PREFIX in DECIDED_BY_PREFIXES, (
    "human-only invariant prefix must be a member of canonical "
    "DECIDED_BY_PREFIXES; pattern 73 SSOT lockstep failure"
)


def _validate_polarity_pairing(polarity: str, canonical_market_id: int | None) -> None:
    """Validate the polarity ↔ canonical_market_id pairing rule.

    Raises ValueError if:
        - ``polarity == 'MUST_MATCH'`` but ``canonical_market_id is None``.
        - ``polarity == 'MUST_NOT_MATCH'`` but
          ``canonical_market_id is not None``.

    The DDL CHECK ``ck_canonical_match_overrides_polarity_pairing`` is
    defense-in-depth; this CRUD-layer guard surfaces the violation
    BEFORE INSERT with a clear ValueError rather than letting psycopg2
    raise a generic CheckViolation.
    """
    if polarity == "MUST_MATCH" and canonical_market_id is None:
        raise ValueError(
            "polarity='MUST_MATCH' requires canonical_market_id to be "
            "non-NULL; got canonical_market_id=None.  MUST_MATCH means "
            "'this canonical_market_id IS the right canonical for this "
            "platform_market'; the pointer is mandatory."
        )
    if polarity == "MUST_NOT_MATCH" and canonical_market_id is not None:
        raise ValueError(
            f"polarity='MUST_NOT_MATCH' requires canonical_market_id to "
            f"be NULL; got canonical_market_id={canonical_market_id!r}.  "
            "MUST_NOT_MATCH means 'this platform_market is NOT in any "
            "canonical group'; the canonical_market_id pointer is "
            "meaningless and must be NULL."
        )


def _validate_human_only_actor(*, param_name: str, value: str) -> None:
    """Validate that an actor attribution starts with the 'human:' prefix.

    Raises ValueError if value does not start with 'human:'.  Length-bound
    enforcement (``len(value) <= 64`` matching VARCHAR(64) column boundary)
    is also at the CRUD boundary per #1085 finding #3.
    """
    if not value.startswith(_HUMAN_ONLY_PREFIX):
        raise ValueError(
            f"{param_name}={value!r} must start with the {_HUMAN_ONLY_PREFIX!r} "
            f"prefix; overrides are human-decided by definition (the "
            f"manual_v1-on-human-decided-actions convention).  Members of "
            f"DECIDED_BY_PREFIXES other than 'human:' are accepted by "
            f"canonical_match_log but rejected here."
        )
    if len(value) > _CREATED_BY_MAX_LENGTH:
        raise ValueError(
            f"{param_name} length {len(value)} exceeds "
            f"VARCHAR({_CREATED_BY_MAX_LENGTH}) column boundary; got "
            f"{value!r}"
        )


# =============================================================================
# canonical_match_overrides — CREATE
# =============================================================================


def create_override(
    *,
    platform_market_id: int,
    canonical_market_id: int | None,
    polarity: str,
    reason: str,
    created_by: str,
) -> int:
    """Create an override row + write the canonical_match_log audit row.

    Atomic two-table write: BOTH the override INSERT and the
    canonical_match_log INSERT commit in a SINGLE transaction — both
    succeed or both roll back.  Previously sequential per Glokta F1
    (slot 0074 review); refactored to atomic via the cursor-aware
    ``_append_match_log_row_in_cursor`` helper exposed by slot 0073's
    crud_canonical_match_log module.

    Per build spec § 4b: every override-touching event lands a log row in
    the unified audit stream with action='override' (the discriminator
    between create-vs-delete is in the note column's "deleted: <reason>"
    prefix on delete; create-time notes are the operator's reason text).

    Validation:
        - ``polarity`` MUST be in ``POLARITY_VALUES`` (Pattern 73 SSOT
          real-guard validation).
        - polarity-canonical_market_id pairing (raises ValueError BEFORE
          INSERT; DDL CHECK is defense-in-depth):
            * polarity='MUST_NOT_MATCH' AND canonical_market_id IS None
            * polarity='MUST_MATCH' AND canonical_market_id IS NOT None
            * any other combination: ValueError.
        - ``created_by`` MUST start with ``'human:'`` prefix (overrides
          are human-only per Holden Item 1 P1 + the manual_v1-on-human-
          decided-actions convention).
        - ``len(created_by) <= 64`` (boundary validation per #1085
          finding #3 inheritance).
        - ``reason.strip() != ""`` rejects empty/whitespace-only per
          #1085 finding #7 inheritance (slot-0072 retire_reason="" empty-
          string-acceptance pattern).  NOTE: the DDL CHECK
          ``ck_canonical_match_overrides_reason_nonempty`` uses
          ``length(trim(reason)) > 0`` — PostgreSQL's default
          ``trim(text)`` strips ONLY the space character, not the broader
          Python ``str.strip()`` whitespace set (tabs, newlines, etc.).
          The asymmetry is intentional defense-in-depth: Python is the
          primary defense (catches all unicode whitespace); the DDL is
          the secondary guard against direct-SQL bypass with empty/
          spaces input.
        - psycopg2 surfaces UNIQUE violation on duplicate
          ``platform_market_id`` (at most ONE override per platform
          market per the table's UNIQUE constraint).

    Side-effects (atomic — same transaction):
        - INSERT into canonical_match_overrides.
        - INSERT into canonical_match_log with action='override',
          link_id=NULL (overrides are independent of any link),
          platform_market_id=override.platform_market_id,
          canonical_market_id=override.canonical_market_id (NULL for
          MUST_NOT_MATCH), algorithm_id=manual_v1.id (the convention
          placeholder), decided_by=created_by, note=reason.

    Args:
        platform_market_id: INTEGER FK into ``markets.id``; CASCADE on
            platform-row deletion.
        canonical_market_id: BIGINT FK into ``canonical_markets.id``;
            NULL for MUST_NOT_MATCH; RESTRICT on canonical-row deletion
            (operator must retire override first).
        polarity: VARCHAR(16) discriminator; MUST be in POLARITY_VALUES.
        reason: TEXT operator-readable explanation; non-empty after
            strip().
        created_by: VARCHAR(64) NOT NULL actor attribution; MUST start
            with 'human:'; MUST be <= 64 chars.

    Returns:
        The BIGSERIAL ``id`` of the newly-inserted override row.

    Raises:
        ValueError: validation failure (polarity vocabulary, polarity-
            pairing rule, human-only prefix, length, empty reason).
        psycopg2.errors.UniqueViolation: platform_market_id already has
            an override (use delete_override + create_override to
            replace).
        psycopg2.errors.ForeignKeyViolation: platform_market_id or
            canonical_market_id references a non-existent row.

    Example:
        >>> override_id = create_override(
        ...     platform_market_id=42,
        ...     canonical_market_id=7,
        ...     polarity="MUST_MATCH",
        ...     reason="Operator confirmed canonical for ambiguous market",
        ...     created_by="human:eric",
        ... )
        # INSERT into canonical_match_overrides + INSERT into
        # canonical_match_log (action='override') both committed atomically.
    """
    # ---- Pattern 73 SSOT real-guard validation -------------------------------
    if polarity not in POLARITY_VALUES:
        raise ValueError(
            f"polarity {polarity!r} not in canonical POLARITY_VALUES "
            f"{POLARITY_VALUES!r}; pattern 73 SSOT vocabulary violation"
        )

    # Polarity-pairing rule (raises BEFORE INSERT).
    _validate_polarity_pairing(polarity, canonical_market_id)

    # human-only invariant + length boundary.
    _validate_human_only_actor(param_name="created_by", value=created_by)

    # Empty/whitespace-only reason rejected per #1085 finding #7.  Python's
    # ``str.strip()`` covers the broader unicode whitespace set (tabs,
    # newlines, etc.); the DDL CHECK ``length(trim(reason)) > 0`` strips
    # only the space character — the asymmetry is intentional defense-in-
    # depth (Python is primary; DDL is secondary against direct-SQL
    # bypass with empty/spaces input).
    if reason.strip() == "":
        raise ValueError(
            f"reason cannot be empty (after .strip()); got {reason!r}.  "
            "Operators MUST supply a substantive explanation; an empty "
            "audit trail explanation is unacceptable for human-decided "
            "overrides (Pattern 73 SSOT bidirectional anchoring with the "
            "ck_canonical_match_overrides_reason_nonempty DDL CHECK)."
        )

    # ---- Atomic two-table write ---------------------------------------------
    # Both the override INSERT and the canonical_match_log INSERT execute
    # in the SAME cursor / transaction — both commit or both roll back.
    # See Glokta F1 P1 (slot 0074 review) for the prior sequential-cursor
    # incident this refactor closes.
    algorithm_id = get_manual_v1_algorithm_id()

    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO canonical_match_overrides (
                platform_market_id, canonical_market_id, polarity,
                reason, created_by
            ) VALUES (
                %s, %s, %s, %s, %s
            )
            RETURNING id
            """,
            (
                platform_market_id,
                canonical_market_id,
                polarity,
                reason,
                created_by,
            ),
        )
        row = cur.fetchone()
        override_id = cast("int", row["id"])

        # Audit-ledger write — manual_v1-on-human-decided-actions
        # convention.  In-cursor variant per Glokta F1: log INSERT runs
        # on the SAME transaction as the override INSERT above.
        _append_match_log_row_in_cursor(
            cur,
            link_id=None,  # overrides are independent of any link
            platform_market_id=platform_market_id,
            canonical_market_id=canonical_market_id,
            action="override",
            confidence=None,  # human override has no algorithmic confidence
            algorithm_id=algorithm_id,  # manual_v1.id placeholder
            features=None,
            prior_link_id=None,
            decided_by=created_by,
            note=reason,
        )

    return override_id


# =============================================================================
# canonical_match_overrides — DELETE
# =============================================================================


def delete_override(
    override_id: int,
    *,
    deleted_by: str,
    reason: str,
) -> None:
    """Hard-delete an override row + write the canonical_match_log audit row.

    Atomic two-table write: the SELECT pre-DELETE attribution lookup, the
    DELETE itself, and the canonical_match_log INSERT all execute in a
    SINGLE transaction — all succeed or all roll back.  Previously
    sequential per Glokta F1 (slot 0074 review); refactored to atomic.

    Why action='override' (not 'override_delete' / 'override_remove'):
    the 7-value action vocabulary is fixed by slot 0073 (per session-80
    PM adjudication of Open Item B); deletion is just another override-
    touching event in the unified audit stream.  The note column carries
    the discriminator via the "deleted: <reason>" prefix convention.

    Validation:
        - ``deleted_by`` MUST start with ``'human:'`` prefix (overrides
          are human-only).
        - ``len(deleted_by) <= 64`` (boundary validation per #1085
          finding #3 inheritance).
        - ``reason.strip() != ""`` (audit trail requires explanation).
        - ``override_id`` must exist; LookupError raised before SQL DELETE
          silently affects 0 rows.

    Side-effects (atomic):
        - SELECT FROM canonical_match_overrides WHERE id = override_id
          (attribution pre-read).
        - DELETE FROM canonical_match_overrides WHERE id = override_id.
        - INSERT into canonical_match_log with action='override',
          link_id=NULL, platform_market_id=<old>, canonical_market_id=
          <old>, algorithm_id=manual_v1.id, decided_by=deleted_by,
          note=f"deleted: {reason}".

    Args:
        override_id: BIGSERIAL ``canonical_match_overrides.id`` to delete.
        deleted_by: VARCHAR(64) NOT NULL actor attribution; MUST start
            with 'human:'; MUST be <= 64 chars.
        reason: TEXT operator-readable explanation for the deletion;
            non-empty after strip().

    Raises:
        ValueError: validation failure (human-only prefix, length, empty
            reason).
        LookupError: ``override_id`` does not exist.
    """
    # ---- Validation ----------------------------------------------------------
    _validate_human_only_actor(param_name="deleted_by", value=deleted_by)

    if reason.strip() == "":
        raise ValueError(
            f"reason cannot be empty (after .strip()); got {reason!r}.  "
            "Audit trail requires a substantive deletion explanation."
        )

    # ---- Atomic SELECT + DELETE + audit-log INSERT --------------------------
    # All three statements execute on the same cursor / transaction per
    # Glokta F1 P1 (slot 0074 review): pre-DELETE attribution read, the
    # DELETE itself, and the audit log INSERT either all commit or all
    # roll back.
    algorithm_id = get_manual_v1_algorithm_id()

    with get_cursor(commit=True) as cur:
        # Resolve attribution from the existing row before DELETE.
        cur.execute(
            """
            SELECT platform_market_id, canonical_market_id, polarity
            FROM canonical_match_overrides
            WHERE id = %s
            """,
            (override_id,),
        )
        existing = cur.fetchone()
        if existing is None:
            raise LookupError(
                f"override_id {override_id} does not exist in canonical_match_overrides"
            )
        platform_market_id = cast("int", existing["platform_market_id"])
        canonical_market_id = cast("int | None", existing["canonical_market_id"])

        cur.execute(
            "DELETE FROM canonical_match_overrides WHERE id = %s",
            (override_id,),
        )

        # Audit-ledger write — manual_v1-on-human-decided-actions
        # convention.  Note column carries the "deleted: <reason>"
        # discriminator prefix.  In-cursor variant per Glokta F1.
        _append_match_log_row_in_cursor(
            cur,
            link_id=None,
            platform_market_id=platform_market_id,
            canonical_market_id=canonical_market_id,
            action="override",
            confidence=None,
            algorithm_id=algorithm_id,
            features=None,
            prior_link_id=None,
            decided_by=deleted_by,
            note=f"deleted: {reason}",
        )


# =============================================================================
# canonical_match_overrides — READ OPERATIONS
# =============================================================================


def get_override(override_id: int) -> dict[str, Any] | None:
    """Read a single override row by id.  Returns None if not found."""
    query = """
        SELECT id, platform_market_id, canonical_market_id, polarity,
               reason, created_by, created_at
        FROM canonical_match_overrides
        WHERE id = %s
    """
    return fetch_one(query, (override_id,))


def get_override_for_platform_market(
    platform_market_id: int,
) -> dict[str, Any] | None:
    """Get the override (if any) for a given platform_market_id.

    At most one override per platform_market_id (UNIQUE constraint
    enforces).  Returns None if no override exists.

    Hot path for the matching layer (Cohort 5+): "before computing an
    algorithmic match, check whether an operator override exists."
    Backed by the UNIQUE constraint's underlying index.
    """
    query = """
        SELECT id, platform_market_id, canonical_market_id, polarity,
               reason, created_by, created_at
        FROM canonical_match_overrides
        WHERE platform_market_id = %s
    """
    return fetch_one(query, (platform_market_id,))


def get_overrides_by_polarity(polarity: str, limit: int = 100) -> list[dict[str, Any]]:
    """Alert-query hot path: 'show me all <polarity> overrides'.

    Pattern 73 SSOT real-guard validation: ``polarity`` is checked
    against ``POLARITY_VALUES`` before SQL, raising ``ValueError`` for
    unknown values.

    Args:
        polarity: VARCHAR(16) discriminator; MUST be in POLARITY_VALUES.
        limit: Maximum rows returned.  Defaults to 100.

    Returns:
        List of full override row dicts (possibly empty), ordered by
        ``created_at DESC`` (most-recent first).

    Raises:
        ValueError: ``polarity`` not in ``POLARITY_VALUES``.
    """
    if polarity not in POLARITY_VALUES:
        raise ValueError(
            f"polarity {polarity!r} not in canonical POLARITY_VALUES "
            f"{POLARITY_VALUES!r}; pattern 73 SSOT vocabulary violation"
        )

    query = """
        SELECT id, platform_market_id, canonical_market_id, polarity,
               reason, created_by, created_at
        FROM canonical_match_overrides
        WHERE polarity = %s
        ORDER BY created_at DESC
        LIMIT %s
    """
    return fetch_all(query, (polarity, limit))


# =============================================================================
# Sentinel: POLARITY_VALUES + DECIDED_BY_PREFIXES are imported and USED above
# in real-guard ``ValueError``-raising validation (create_override + module-
# load `_HUMAN_ONLY_PREFIX in DECIDED_BY_PREFIXES` assertion +
# get_overrides_by_polarity).  If a future refactor drops the validation,
# the imports become unused and ruff (F401) will fire — closing the side-
# effect-only-import drift surface that #1085 finding #2 strengthening
# prevents.  This is the canonical strengthening of slot-0072's
# LINK_STATE_VALUES side-effect-only-import convention.
# =============================================================================
