"""CRUD operations for canonical_match_log — THE matching-layer audit ledger.

Cohort 3 third slot of the canonical-layer foundation (ADR-118 v2.41
amendment + v2.42 sub-amendment B + session-78 Cohort 3 design council +
session-80 S82 design-stage P41 council outcomes inherited from slot 0072
+ session-81 Holden re-engagement memo applied to the build spec).
Sister module to ``crud_canonical_market_links.py`` and
``crud_canonical_event_links.py``; uses the same raw-psycopg2 +
``get_cursor`` / ``fetch_one`` / ``fetch_all`` + RealDictCursor +
heavy-docstring conventions.

Tables covered:
    - ``canonical_match_log`` (Migration 0073) — append-only audit ledger
      for the matching layer.  Every match decision in the system writes
      one row here: ``link`` / ``unlink`` / ``relink`` / ``quarantine``
      on the link tables (slot 0072), plus ``override`` /
      ``review_approve`` / ``review_reject`` on slot 0074's review +
      override tables.

THE RESTRICTED API SURFACE — APPEND-ONLY VIA APPLICATION DISCIPLINE:

    This module exposes EXACTLY ONE write function:
    ``append_match_log_row()``.  There are NO ``update_*`` functions, NO
    ``delete_*`` functions, NO ``upsert_*`` functions.  This is by design:
    the audit ledger is append-only, and the discipline lives in this
    module's API surface (Migration 0073 docstring § "Append-only via
    application discipline").

    The trigger-enforced version (BEFORE UPDATE/DELETE → ``RAISE
    EXCEPTION 'canonical_match_log is append-only'``) is queued for slot
    0090 after a 30-day production soak validates that the application-
    discipline approach is sufficient (per L10 + Cohort 3 design council
    Elrond E:90).  Until then:

        - DO NOT add ``update_*`` / ``delete_*`` / ``upsert_*`` helpers
          to this module without an ADR amendment.
        - DO NOT write ad-hoc ``UPDATE canonical_match_log`` /
          ``DELETE FROM canonical_match_log`` SQL anywhere outside the
          slot-0073 migration's downgrade (Pattern 73 violation —
          consumers would drift; future S81 grep audits will sweep for
          this).
        - The ``append_match_log_row()`` function is the ONLY sanctioned
          write path; future log-readers can rely on the function's
          contract (validation + invariant enforcement).

Pattern 73 SSOT discipline (CLAUDE.md Critical Pattern #8):

    Two vocabularies are SSOT-anchored at
    ``src/precog/database/constants.py``:

        ``ACTION_VALUES``         — 7-value ``action`` discriminator
                                    vocabulary (link / unlink / relink /
                                    quarantine / override /
                                    review_approve / review_reject).
                                    Inline DDL CHECK on
                                    canonical_match_log.action cites this
                                    constant by name; this module uses it
                                    in REAL-GUARD validation —
                                    ``if action not in ACTION_VALUES:
                                    raise ValueError(...)``.

        ``DECIDED_BY_PREFIXES``   — 3-prefix actor taxonomy
                                    (``human:`` / ``service:`` /
                                    ``system:``).  CHECK constraint cannot
                                    enforce free-text format; this module's
                                    real-guard validation in
                                    ``append_match_log_row()`` is the
                                    discipline.

    The slot-0072 ``LINK_STATE_VALUES`` import convention used
    ``# noqa: F401`` (side-effect-only import asserting vocabulary home).
    Slot 0073 INTENTIONALLY upgrades this convention per #1085 finding #2:
    both ``ACTION_VALUES`` and ``DECIDED_BY_PREFIXES`` are imported and
    USED in real-guard ``ValueError``-raising validation.  The side-
    effect-only convention does not survive into the new slot.

decided_by value-set convention (Pattern 73 SSOT pointer — Uhura S82
Builder consideration #5):

    The canonical home is ``constants.py:DECIDED_BY_PREFIXES``; this
    docstring is the pointer (NOT a duplicate rule statement per
    CLAUDE.md item #8).  Conventions:

        ``'human:<username>'``    — human-driven action.  Override rows
                                    always use this prefix.
        ``'service:<svc-name>'``  — autonomous matcher service (Cohort 5+).
        ``'system:<context>'``    — seed / migration / system writes.

    Length-bound enforcement (``len(decided_by) <= 64`` matching VARCHAR(64)
    column boundary) lives in ``append_match_log_row()`` validation per
    #1085 finding #3 (the slot-0072 ``retire_reason`` length-not-validated
    case the review surfaced; slot 0073 inherits the lesson by
    surfacing the boundary at the CRUD layer rather than letting psycopg2
    surface a generic StringDataRightTruncation error).

manual_v1 algorithm_id-on-override convention (Uhura S82 Builder
consideration #7):

    Override rows in canonical_match_log have ``action='override'`` and
    ``algorithm_id = manual_v1.id`` (the row seeded by Migration 0071).
    This is a CATEGORY-FIT CONVENTION, not a fact:

        - Overrides are human-decided; ``decided_by='human:<username>'``
          carries the actual actor identity.
        - ``algorithm_id`` is NOT NULL on canonical_match_log; the
          ``manual_v1`` placeholder lets future log-readers JOIN to
          ``match_algorithm`` for category metadata.
        - Future log-readers MUST NOT mistake
          ``algorithm_id = manual_v1.id`` on ``action='override'`` rows
          for "the manual_v1 algorithm decided this override."  The
          ``decided_by`` column is the source-of-truth for actor identity.

    This convention is enforced by the matching layer (Cohort 5+
    application code) — not by this module's CRUD validation.  The
    schema cannot constrain it (algorithm_id NOT NULL is a schema
    invariant; "must equal manual_v1.id when action='override'" is
    policy-level).

v2.42 sub-amendment B canonical query template (Uhura S82 Builder
consideration #6):

    Operator runbook query — "find all log rows for platform_market X
    including post-link-delete (orphan) rows":

        SELECT *
        FROM canonical_match_log
        WHERE platform_market_id = $1
          AND action IN ('link', 'unlink', 'relink', 'quarantine')
        ORDER BY decided_at DESC;

    WHY: ``link_id`` is ON DELETE SET NULL.  After a link is deleted, log
    rows survive with ``link_id=NULL`` but full attribution preserved in
    ``(platform_market_id, canonical_market_id, decided_at, decided_by,
    algorithm_id)``.  A naive INNER JOIN on link_id silently drops the
    historical orphans; the canonical approach uses platform_market_id
    directly (which has no FK and cannot go NULL on link deletion).

    The ``get_match_log_for_link(link_id, include_orphans=True)`` helper
    surfaces the orphan-aware query through the link_id projection (using
    a UNION on the historical attribution tuple); ``get_match_log_for_
    platform_market()`` is the canonical operator-facing form.

L33 dedicated CRUD module restriction:

    All write paths to canonical_match_log MUST go through this module's
    ``append_match_log_row()`` function.  There is NO direct-SQL escape
    hatch in the public API; future call sites adding ad-hoc INSERT SQL
    bypass the validation layer (Pattern 73 SSOT vocabulary checks +
    decided_by length bound + decided_by prefix discipline +
    confidence bound) and represent a Pattern 73 violation.  S81 grep
    audits sweep for direct INSERT into canonical_match_log outside this
    module.

Reference:
    - ``docs/foundation/ARCHITECTURE_DECISIONS.md`` ADR-118 v2.41 +
      v2.42 sub-amendment B
    - ``src/precog/database/alembic/versions/0073_canonical_match_log.py``
    - ``src/precog/database/crud_canonical_market_links.py`` (style
      reference)
    - ``src/precog/database/constants.py`` ``ACTION_VALUES`` +
      ``DECIDED_BY_PREFIXES``
    - ``memory/build_spec_0073_pm_memo.md`` (binding build spec)
    - ``memory/holden_reengagement_0073_memo.md`` (Holden re-engagement
      verdict + amendments)
"""

import json
import logging
from decimal import Decimal
from typing import Any, cast

from .connection import fetch_all, get_cursor
from .constants import ACTION_VALUES, DECIDED_BY_PREFIXES

logger = logging.getLogger(__name__)


# Maximum allowed length for ``decided_by`` matches the DDL column boundary
# (``VARCHAR(64)``).  Centralizing the constant here lets callers reference it
# without re-deriving the magic number; surfaced to module scope rather than
# duplicated inside the validation function.
_DECIDED_BY_MAX_LENGTH = 64


# =============================================================================
# CANONICAL MATCH LOG — APPEND-ONLY WRITE PATH
# =============================================================================


def append_match_log_row(
    *,
    link_id: int | None,
    platform_market_id: int,
    canonical_market_id: int | None,
    action: str,
    confidence: Decimal | None,
    algorithm_id: int,
    features: dict[str, Any] | None,
    prior_link_id: int | None,
    decided_by: str,
    note: str | None = None,
) -> int:
    """Append one row to canonical_match_log.  THIS IS THE ONLY SANCTIONED WRITE PATH.

    The audit ledger is append-only.  This function performs CRUD-layer
    validation that complements the DDL CHECK constraints (Pattern 73 SSOT
    + #1085 finding #2 real-guard strengthening + #1085 finding #3
    boundary-validation lesson):

        - ``action`` MUST be in ``ACTION_VALUES`` (Pattern 73 SSOT real-
          guard validation; raises ``ValueError`` before SQL).
        - ``decided_by`` MUST start with one of ``DECIDED_BY_PREFIXES``
          (Pattern 73 SSOT real-guard validation).
        - ``len(decided_by)`` MUST be ``<= 64`` (boundary validation per
          #1085 finding #3 — surfaces a clear ``ValueError`` before
          psycopg2 raises a generic StringDataRightTruncation).
        - ``confidence`` MUST be NULL OR in [0, 1] AND NOT ``Decimal('NaN')``
          (CRUD-layer parity with the DDL CHECK; ``Decimal('NaN')`` passes
          the ``>=`` / ``<=`` comparisons silently — explicit NaN guard
          required).
        - All FK columns are passed through unchanged; psycopg2 surfaces
          FK violations as ``ForeignKeyViolation``.

    Args:
        link_id: BIGSERIAL FK into ``canonical_market_links.id``.  May be
            NULL (orphan row post-link-deletion via v2.42 sub-amendment B
            SET NULL semantics, OR pre-link rows like ``action='override'``
            that target a (platform, canonical) pair before any link
            exists).  Validated as int-or-None at the type level; FK
            integrity surfaced at the SQL layer.
        platform_market_id: INTEGER NOT NULL.  Deliberately no FK at the DB
            layer (L9); CRUD callers MUST pass a valid platform-tier
            ``markets.id`` value.  No FK validation here — the column's
            survival semantics depend on the absence of an FK (audit log
            outlives the platform row).
        canonical_market_id: BIGINT FK into ``canonical_markets.id``.
            NULL allowed for override rows where polarity = MUST_NOT_MATCH
            (per Uhura logging-frame argument).  ON DELETE SET NULL per
            Holden P1 catch.
        action: VARCHAR(16) discriminator.  MUST be in ``ACTION_VALUES``.
        confidence: NUMERIC(4,3) algorithm score.  NULL allowed (human
            overrides have no algorithmic confidence).  Decimal-only per
            CLAUDE.md Critical Pattern #1; never float.
        algorithm_id: BIGINT FK into ``match_algorithm.id``.  NOT NULL —
            human-decided override rows use ``manual_v1.id`` per the
            manual_v1-on-override convention (see module docstring).
        features: JSONB free-form input snapshot at decision time.  NULL
            acceptable; schema deferred to Cohort 5+.
        prior_link_id: BIGINT FK into ``canonical_market_links.id``.
            For ``action='relink'`` and ``action='unlink'`` rows: pointer
            to the predecessor link row.  NULL for fresh ``action='link'``
            rows where there is no predecessor.  ON DELETE SET NULL per
            Holden P3 deliberate spec-strengthening.
        decided_by: VARCHAR(64) NOT NULL actor attribution.  MUST start
            with one of ``DECIDED_BY_PREFIXES``; MUST be <= 64 chars.
        note: Free-text TEXT operator-readable explanation.  NULL
            acceptable; no boundary enforcement (TEXT is unbounded).

    Returns:
        The BIGSERIAL ``id`` of the newly-inserted log row.

    Raises:
        ValueError: validation failure (action / decided_by / confidence
            domain errors) — surfaced before SQL.
        psycopg2.errors.ForeignKeyViolation: link_id, canonical_market_id,
            algorithm_id, or prior_link_id references a non-existent row.
        psycopg2.errors.CheckViolation: should not occur in practice
            (CRUD validation precedes DDL CHECK), but surfaces if the DDL
            CHECK and the Python constant drift apart (Pattern 73 SSOT
            failure mode).

    Example:
        >>> log_id = append_match_log_row(
        ...     link_id=link_id,
        ...     platform_market_id=42,
        ...     canonical_market_id=7,
        ...     action="link",
        ...     confidence=Decimal("0.987"),
        ...     algorithm_id=algorithm_id,
        ...     features={"source": "keyword_jaccard_v1"},
        ...     prior_link_id=None,
        ...     decided_by="service:matching-v1",
        ...     note="initial match",
        ... )

    Educational Note:
        The two-table-write pattern from build spec § 2 design note (Miles
        S82 consideration #3) ships in Cohort 5+ matcher code: the
        matcher writes BOTH a link-table INSERT (slot 0072) AND a log
        INSERT here in a single ``BEGIN ... COMMIT`` transaction.  The
        atomic transaction is the application-layer correctness contract;
        ``canonical_match_log.link_id ON DELETE SET NULL`` deliberately
        decouples the lifecycle so a hard-deleted link (rare; mostly
        test cleanup paths) doesn't break the audit history.

    Reference:
        - Migration 0073 (table DDL + CHECK constraints)
        - ``constants.py`` ``ACTION_VALUES`` + ``DECIDED_BY_PREFIXES``
        - Build spec § 4 (CRUD API surface specification)
        - #1085 finding #2 (real-guard validation strengthening)
        - #1085 finding #3 (boundary validation lesson from slot 0072
          ``retire_reason``)
    """
    # ---- Pattern 73 SSOT real-guard validation -------------------------------
    # action must be in the canonical 7-value vocabulary.  ValueError raised
    # before SQL so callers see a clear validation message rather than a
    # CheckViolation from psycopg2 (which would still fire if validation here
    # somehow passed — that's the lockstep guarantee Pattern 73 SSOT provides).
    if action not in ACTION_VALUES:
        raise ValueError(
            f"action {action!r} not in canonical ACTION_VALUES "
            f"{ACTION_VALUES!r}; pattern 73 SSOT vocabulary violation"
        )

    # decided_by prefix discipline: must start with one of the canonical
    # actor-taxonomy prefixes from constants.py:DECIDED_BY_PREFIXES.  CHECK
    # cannot enforce string format, so this is the discipline.
    if not any(decided_by.startswith(p) for p in DECIDED_BY_PREFIXES):
        raise ValueError(
            f"decided_by {decided_by!r} must start with one of "
            f"DECIDED_BY_PREFIXES {DECIDED_BY_PREFIXES!r}; "
            "pattern 73 SSOT vocabulary violation"
        )

    # decided_by length boundary per #1085 finding #3: surface a clear error
    # at the CRUD layer rather than letting psycopg2 raise the generic
    # StringDataRightTruncation when the value exceeds VARCHAR(64).
    if len(decided_by) > _DECIDED_BY_MAX_LENGTH:
        raise ValueError(
            f"decided_by length {len(decided_by)} exceeds "
            f"VARCHAR({_DECIDED_BY_MAX_LENGTH}) column boundary; got {decided_by!r}"
        )

    # confidence bound check — CRUD-layer parity with DDL CHECK constraint.
    # CLAUDE.md Critical Pattern #1 (Decimal Precision) enforced at the CRUD
    # boundary: float silently satisfies >= 0 and <= 1 (Python comparison
    # operators happily compare float vs Decimal), so without an explicit
    # isinstance check a caller passing `confidence=0.5` would slip past the
    # validation entirely; worse, `confidence.is_nan()` on a float raises
    # AttributeError (cryptic exception type, no boundary signal). The
    # isinstance guard surfaces the type violation as a clear TypeError before
    # any value-level check runs. (Ripley P1 sentinel finding, session 81.)
    # Decimal('NaN') silently passes >= and <= comparisons, so explicit guard.
    if confidence is not None:
        if not isinstance(confidence, Decimal):
            raise TypeError(
                f"confidence must be Decimal or None per CLAUDE.md Critical "
                f"Pattern #1 (no float in probability paths); got "
                f"{type(confidence).__name__}={confidence!r}"
            )
        if confidence.is_nan():
            raise ValueError(f"confidence must not be Decimal('NaN'); got {confidence!r}")
        if confidence < Decimal("0") or confidence > Decimal("1"):
            raise ValueError(f"confidence must be in [0, 1] or None; got {confidence!r}")

    # ---- The append (single INSERT, RETURNING id) ----------------------------
    # No UPDATE / DELETE / UPSERT — this is the ONLY sanctioned write path.
    # features dict is serialized to JSON text and cast to JSONB at the SQL
    # layer (`%s::jsonb` in the query below).  Going through json.dumps gives
    # us deterministic encoding regardless of psycopg2 adapter registration
    # state, which keeps the test mocks simple.
    features_param: str | None = None if features is None else json.dumps(features)

    query = """
        INSERT INTO canonical_match_log (
            link_id, platform_market_id, canonical_market_id, action,
            confidence, algorithm_id, features, prior_link_id, decided_by,
            note
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s::jsonb, %s, %s,
            %s
        )
        RETURNING id
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            query,
            (
                link_id,
                platform_market_id,
                canonical_market_id,
                action,
                confidence,
                algorithm_id,
                features_param,
                prior_link_id,
                decided_by,
                note,
            ),
        )
        row = cur.fetchone()
    return cast("int", row["id"])


# =============================================================================
# CANONICAL MATCH LOG — READ OPERATIONS
# =============================================================================


def get_match_log_for_platform_market(
    platform_market_id: int,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Get the canonical_match_log rows for a platform market, newest-first.

    This is the **operator audit hot path** — when an operator asks
    "what's the decision history for this Kalshi market?", they call this
    function.  Returns rows in descending ``decided_at`` order (most-recent
    first); the underlying ``idx_canonical_match_log_decided_at`` index +
    ``idx_canonical_match_log_platform_market_id`` index keep this O(log n)
    + limit-bounded regardless of total log-table size.

    The query filters by ``platform_market_id`` (which has NO FK and
    cannot go NULL on link deletion — see L9 + v2.42 sub-amendment B
    canonical query template in the migration docstring + module
    docstring).  This makes the query orphan-aware by construction:
    rows whose ``link_id`` was SET NULL by a link DELETE are still
    returned, with full attribution preserved in
    ``(platform_market_id, canonical_market_id, decided_at, decided_by,
    algorithm_id)``.

    Args:
        platform_market_id: INTEGER target into the platform-tier
            ``markets`` table (``markets.id``).  No FK at the log-table
            layer; pass any valid platform-tier id.
        limit: Maximum rows returned.  Defaults to 50 — large enough for
            most operator runbook queries, small enough to bound the
            per-query overhead.  Pagination beyond 50 rows is not
            currently supported (file an issue if a use case justifies it).

    Returns:
        List of full row dicts (possibly empty), ordered by ``decided_at
        DESC``.  Keys: id, link_id, platform_market_id, canonical_market_id,
        action, confidence, algorithm_id, features, prior_link_id,
        decided_by, decided_at, note, created_at.

    Example:
        >>> log_rows = get_match_log_for_platform_market(42)
        >>> latest_decision = log_rows[0] if log_rows else None
        >>> if latest_decision:
        ...     print(f"Last action: {latest_decision['action']} by "
        ...           f"{latest_decision['decided_by']}")

    Reference:
        - Migration 0073 (idx_canonical_match_log_decided_at +
          idx_canonical_match_log_platform_market_id)
        - Module docstring v2.42 sub-amendment B canonical query template
    """
    query = """
        SELECT id, link_id, platform_market_id, canonical_market_id,
               action, confidence, algorithm_id, features, prior_link_id,
               decided_by, decided_at, note, created_at
        FROM canonical_match_log
        WHERE platform_market_id = %s
        ORDER BY decided_at DESC
        LIMIT %s
    """
    return fetch_all(query, (platform_market_id, limit))


def get_match_log_for_link(
    link_id: int,
    include_orphans: bool = False,
) -> list[dict[str, Any]]:
    """Get the canonical_match_log rows for a specific link.

    Two query modes per the v2.42 sub-amendment B canonical query template:

        ``include_orphans=False`` (default): exact-match on ``link_id =
        %s``.  Returns rows whose ``link_id`` still references the live
        link.  Excludes post-link-delete orphan rows where ``link_id ==
        NULL`` (the link was hard-deleted via v2.42 sub-amendment B SET
        NULL).

        ``include_orphans=True``: returns the live-link rows AS WELL AS
        the orphan-attribution rows recovered via the
        ``(platform_market_id, canonical_market_id, decided_at,
        decided_by, algorithm_id)`` tuple lookup against the link's row.

    Most callers want ``include_orphans=False`` (the default).
    Operator-runbook flows reconstructing post-deletion history use
    ``include_orphans=True``.

    Args:
        link_id: BIGSERIAL ``canonical_market_links.id`` to look up.
        include_orphans: When True, also return rows whose ``link_id``
            was SET NULL by a link DELETE but whose attribution tuple
            matches the link's other columns.  Defaults to False.

    Returns:
        List of full row dicts (possibly empty), ordered by ``decided_at
        DESC``.

    Example:
        >>> live_rows = get_match_log_for_link(7)
        >>> all_rows = get_match_log_for_link(7, include_orphans=True)
        >>> orphan_count = len(all_rows) - len(live_rows)

    Educational Note:
        ``include_orphans=True`` requires the link row to still exist (so
        we can recover its attribution tuple).  If the link row itself is
        deleted, the attribution must be supplied directly to
        ``get_match_log_for_platform_market()`` instead.

    Reference:
        - Migration 0073 (idx_canonical_match_log_link_id partial index)
        - v2.42 sub-amendment B canonical query template (module docstring)
    """
    if not include_orphans:
        query = """
            SELECT id, link_id, platform_market_id, canonical_market_id,
                   action, confidence, algorithm_id, features,
                   prior_link_id, decided_by, decided_at, note, created_at
            FROM canonical_match_log
            WHERE link_id = %s
            ORDER BY decided_at DESC
        """
        return fetch_all(query, (link_id,))

    # include_orphans=True: the link row's attribution tuple anchors the
    # historical orphans.  We resolve the link's (platform_market_id,
    # canonical_market_id) tuple, then UNION the live-link-id rows with
    # the orphan rows that share the tuple but have link_id IS NULL.
    query = """
        WITH link_attribution AS (
            SELECT id AS lid, platform_market_id, canonical_market_id
            FROM canonical_market_links
            WHERE id = %s
        )
        SELECT cml.id, cml.link_id, cml.platform_market_id,
               cml.canonical_market_id, cml.action, cml.confidence,
               cml.algorithm_id, cml.features, cml.prior_link_id,
               cml.decided_by, cml.decided_at, cml.note, cml.created_at
        FROM canonical_match_log cml
        JOIN link_attribution la
          ON cml.link_id = la.lid
        UNION ALL
        SELECT cml.id, cml.link_id, cml.platform_market_id,
               cml.canonical_market_id, cml.action, cml.confidence,
               cml.algorithm_id, cml.features, cml.prior_link_id,
               cml.decided_by, cml.decided_at, cml.note, cml.created_at
        FROM canonical_match_log cml
        JOIN link_attribution la
          ON cml.link_id IS NULL
         AND cml.platform_market_id = la.platform_market_id
         AND cml.canonical_market_id IS NOT DISTINCT FROM la.canonical_market_id
        ORDER BY decided_at DESC
    """
    return fetch_all(query, (link_id,))


def get_match_log_by_action(
    action: str,
    since: Any,
) -> list[dict[str, Any]]:
    """Get canonical_match_log rows by action discriminator + time window.

    Alert-query support: surfaces rows of a given ``action`` since a
    timestamp.  Useful for Cohort 5+ alerting flows ("how many
    quarantine actions in the last hour?", "any review_reject rows since
    last operator handoff?").

    Pattern 73 SSOT real-guard validation: ``action`` is checked against
    ``ACTION_VALUES`` before SQL, raising ``ValueError`` for unknown
    values.  This catches typos at the read path the same way the write
    path does.

    Args:
        action: VARCHAR(16) discriminator.  MUST be in ``ACTION_VALUES``.
        since: TIMESTAMPTZ lower bound (inclusive).  Pass a
            ``datetime.datetime`` or any psycopg2-compatible timestamp.

    Returns:
        List of full row dicts (possibly empty), ordered by ``decided_at
        DESC``.

    Raises:
        ValueError: ``action`` not in ``ACTION_VALUES`` (Pattern 73 SSOT
            real-guard validation).

    Example:
        >>> from datetime import datetime, timedelta, UTC
        >>> hour_ago = datetime.now(UTC) - timedelta(hours=1)
        >>> recent_quarantines = get_match_log_by_action("quarantine", hour_ago)

    Reference:
        - constants.py ``ACTION_VALUES``
        - Migration 0073 (idx_canonical_match_log_decided_at)
    """
    if action not in ACTION_VALUES:
        raise ValueError(
            f"action {action!r} not in canonical ACTION_VALUES "
            f"{ACTION_VALUES!r}; pattern 73 SSOT vocabulary violation"
        )

    query = """
        SELECT id, link_id, platform_market_id, canonical_market_id,
               action, confidence, algorithm_id, features, prior_link_id,
               decided_by, decided_at, note, created_at
        FROM canonical_match_log
        WHERE action = %s
          AND decided_at >= %s
        ORDER BY decided_at DESC
    """
    return fetch_all(query, (action, since))


# =============================================================================
# Sentinel: ACTION_VALUES + DECIDED_BY_PREFIXES are imported and USED above
# in real-guard ``ValueError``-raising validation (append_match_log_row +
# get_match_log_by_action).  If a future refactor drops the validation, the
# imports become unused and ruff (F401) will fire — closing the side-effect-
# only-import drift surface that #1085 finding #2 strengthening prevents.
# This is the canonical strengthening of slot-0072's LINK_STATE_VALUES
# side-effect-only-import convention (which used a noqa F401 comment to keep
# the import alive purely for vocabulary-home assertion).
# =============================================================================
