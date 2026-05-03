"""CRUD operations for canonical_observations — THE canonical-tier observation parent.

Cohort 4 first slot of the canonical-tier observation pipeline (ADR-118
V2.43 Cohort 4 + session 85 4-agent design council + session 86 PM-composed
build spec at ``memory/build_spec_0078_pm_memo.md``).  Sister module to
``crud_canonical_match_log.py`` (slot 0073) — uses the same restricted-API
discipline (single sanctioned write path, no UPDATE/DELETE/UPSERT helpers,
real-guard validation against Pattern 73 SSOT vocabularies).

Tables covered:
    - ``canonical_observations`` (Migration 0078) — partitioned parent for
      every cross-domain observation in the system.  Append-only via
      application discipline (mirrors slot 0073 precedent).  Per-kind
      projection tables (``weather_observations``, ``poll_releases``,
      etc.) materialize in Cohort 9+; Cohort 4 only exercises the
      ``game_state`` kind.

THE RESTRICTED API SURFACE — APPEND-ONLY VIA APPLICATION DISCIPLINE:

    This module exposes EXACTLY ONE write function:
    ``append_observation_row()``.  There are NO ``update_*`` functions, NO
    ``delete_*`` functions, NO ``upsert_*`` functions, NO bulk-append
    helpers, NO general SELECT helpers.  This is by design:

        - The observation parent is append-only (audit + replay history
          outlives the row's analytical relevance).  Discipline lives in
          this module's API surface (Migration 0078 docstring §
          "Append-only via application discipline").
        - Bulk-append helpers are deferred to Cohort 5+ once ingest-rate
          measurements exist (premature optimization without measured
          throughput is anti-pattern; #1085-finding flavor).
        - General SELECT helpers (``get_observation_by_id``,
          ``query_observations_by_event``, etc.) are added Cohort 5+ as
          consumers materialize.  Slot 0078 ships only the write surface
          because there is no Cohort 4 reader yet (reconciler is a
          separate slot/PR after writer soak per V2.43 micro-delta MD1).

    The trigger-enforced version (BEFORE INSERT/UPDATE/DELETE → ``RAISE
    EXCEPTION 'canonical_observations is append-only'``) is queued for
    a post-soak slot after baseline ingest-rate measurements validate
    that application-discipline is sufficient — same shape as slot
    0073's slot-0090 deferral.  Until then:

        - DO NOT add ``update_*`` / ``delete_*`` / ``upsert_*`` /
          ``bulk_append_*`` helpers to this module without an ADR
          amendment.
        - DO NOT write ad-hoc ``UPDATE canonical_observations`` /
          ``DELETE FROM canonical_observations`` SQL anywhere outside
          the slot-0078 migration's downgrade (Pattern 73 violation —
          consumers would drift).
        - The ``append_observation_row()`` function is the ONLY
          sanctioned write path; future log-readers can rely on the
          function's contract (validation + invariant enforcement).

Pattern 73 SSOT discipline (CLAUDE.md Critical Pattern #8):

    One vocabulary is SSOT-anchored at
    ``src/precog/database/constants.py:OBSERVATION_KIND_VALUES``.  Inline
    DDL CHECK on ``canonical_observations.observation_kind`` cites this
    constant by name; this module uses it in REAL-GUARD validation —
    ``if observation_kind not in OBSERVATION_KIND_VALUES: raise
    ValueError(...)``.  This is the slot-0073-strengthened convention
    (real-guard usage, not side-effect-only ``# noqa: F401``).

    Two additional vocabularies (PARTITION_STRATEGY_VALUES +
    RECONCILIATION_OUTCOME_VALUES) are documented in constants.py for
    Cohort 5+ consumers; this module does not import them because slot
    0078 has no read/reconcile path.

payload_hash derivation rule (Builder open-question #1 resolution):

    SHA-256 of canonicalized JSON.  Canonicalization rule:
    ``json.dumps(payload, sort_keys=True, separators=(',', ':'))``.
    Cohort 4 ships SHA-256; if collision becomes a concern (extremely
    unlikely at observation scale), swap to SHA-3 in a future migration.
    The ``payload_hash`` column is BYTEA so the algorithm swap is non-
    DDL-breaking (column type stays the same; only the hash digest size
    differs, and BYTEA accepts any length).

    Builder may NOT extend the derivation rule (e.g., add per-kind
    salt, normalize specific fields before hashing) without an ADR
    amendment — the Cohort 5+ reconciler will rely on byte-stable
    payload_hash semantics for cross-environment dedup checking.

Composite-FK invariant (V2.43 Item 3 — for future per-kind projections):

    The append function returns ``(id, ingested_at)`` — a composite key
    tuple.  Per-kind projection tables (Cohort 9+) FK INTO
    ``canonical_observations`` MUST use composite-FK shape:

        FOREIGN KEY (canonical_observation_id, observation_ingested_at)
        REFERENCES canonical_observations(id, ingested_at)

    Surrogate ``id`` alone is insufficient — PG cannot route the FK
    lookup to the correct partition without the partition key.  Callers
    persisting the returned tuple as a projection-table FK must store
    BOTH components.  Forward-pointer for Cohort 9+ projection authors.

Reference:
    - ``docs/foundation/ARCHITECTURE_DECISIONS.md`` ADR-118 V2.43
      Cohort 4 (canonical_observations partitioned parent + 5-timestamp
      DDL + composite-FK invariant)
    - ``src/precog/database/alembic/versions/0078_canonical_observations.py``
    - ``src/precog/database/crud_canonical_match_log.py`` (style
      reference + restricted-API discipline precedent)
    - ``src/precog/database/constants.py`` ``OBSERVATION_KIND_VALUES`` +
      ``PARTITION_STRATEGY_VALUES`` + ``RECONCILIATION_OUTCOME_VALUES``
    - ``memory/build_spec_0078_pm_memo.md`` (binding build spec)
    - ``memory/s82_slot_0078_inherited_memo.md`` (S82 INHERITED verdict)
    - ``docs/operations/canonical_observations_runbook.md`` (operator
      runbook for the writer component + partition lifecycle)
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING, Any, cast

from .connection import get_cursor
from .constants import OBSERVATION_KIND_VALUES

if TYPE_CHECKING:
    from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# INTERNAL HELPER — payload_hash derivation
# =============================================================================


def _compute_payload_hash(payload: dict[str, Any]) -> bytes:
    """Compute SHA-256 of canonicalized JSON bytes.

    Canonicalization rule: ``json.dumps(payload, sort_keys=True,
    separators=(',', ':'))``.  Sort_keys ensures key-order independence
    (a payload ``{"a": 1, "b": 2}`` hashes the same as ``{"b": 2,
    "a": 1}``); the compact separators eliminate spurious whitespace
    variance.

    Cohort 4 ships SHA-256.  The ``payload_hash`` column is BYTEA so
    a future algorithm swap (SHA-3) is non-DDL-breaking.

    Args:
        payload: dict to hash.  Must be JSON-serializable; non-
            serializable contents (e.g., datetime objects, custom
            classes) raise ``TypeError`` at ``json.dumps`` time.

    Returns:
        32-byte SHA-256 digest.

    Raises:
        TypeError: payload contains non-JSON-serializable values.

    Example:
        >>> hash_a = _compute_payload_hash({"a": 1, "b": 2})
        >>> hash_b = _compute_payload_hash({"b": 2, "a": 1})
        >>> assert hash_a == hash_b  # key-order independent
        >>> hash_c = _compute_payload_hash({"a": 1, "b": 3})
        >>> assert hash_a != hash_c  # different payload, different hash
    """
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).digest()


# =============================================================================
# CANONICAL OBSERVATIONS — APPEND-ONLY WRITE PATH
# =============================================================================


def append_observation_row(
    *,
    observation_kind: str,
    source_id: int,
    canonical_primary_event_id: int | None,
    payload: dict[str, Any],
    event_occurred_at: datetime | None,
    source_published_at: datetime,
    valid_until: datetime | None = None,
) -> tuple[int, datetime]:
    """Append one row to canonical_observations.  THIS IS THE ONLY SANCTIONED WRITE PATH.

    **V2.45 (slot 0084) update:** the ``canonical_observations.payload``
    column was DROPPED.  Per-kind projection tables (``game_states``,
    ``market_snapshots``, future ``weather_observations`` /
    ``poll_releases`` / ``econ_prints`` / ``news_events``) carry the
    typed source data + JSONB residue where needed.  This function still
    accepts the ``payload`` parameter — it is hashed via SHA-256 to
    produce ``payload_hash`` (the dedup key, retained on the table) but
    is NOT stored on canonical_observations itself.  Callers MUST also
    write the typed projection-table row (Cohort 5+ writer wiring;
    issue #1141) for the typed source data to be persistent.

    **V2.45 (slot 0084) rename:** the
    ``canonical_observations.canonical_event_id`` column was RENAMED to
    ``canonical_primary_event_id`` to make denormalized-as-primary-tag
    semantics explicit.  Many-to-many multi-event tagging lives in the
    new ``canonical_observation_event_links`` table (slot 0084); this
    column is the hot-path read for the "primary event" tag, mirroring
    the ``link_kind = 'primary'`` row in the link table.  The function
    parameter is renamed accordingly.

    The canonical_observations parent is append-only via application
    discipline (mirrors slot 0073 ``canonical_match_log`` precedent).
    This function performs CRUD-layer validation that complements the DDL
    CHECK constraints:

        - ``observation_kind`` MUST be in ``OBSERVATION_KIND_VALUES``
          (Pattern 73 SSOT real-guard validation; raises ``ValueError``
          before SQL).
        - All FK columns are passed through unchanged; psycopg2 surfaces
          FK violations as ``ForeignKeyViolation``.
        - The DDL clock-skew CHECK
          (``source_published_at <= ingested_at + interval '5 minutes'``)
          surfaces at the SQL layer as ``CheckViolation`` if the source's
          claimed publish time is too far ahead of our clock.
        - The DDL bitemporal CHECK
          (``valid_until IS NULL OR valid_until >= valid_at``) surfaces
          as ``CheckViolation`` if the caller passes a ``valid_until``
          earlier than the implicit ``valid_at`` default of ``now()``.
        - Dedup is enforced by the DDL composite UNIQUE on
          ``(source_id, payload_hash, ingested_at)``; a duplicate
          (re-published source observation in the same partition window)
          raises ``UniqueViolation``.

    Composite-FK invariant (V2.43 Item 3): the returned ``(id,
    ingested_at)`` tuple is the composite-PK projection.  Callers
    persisting this as a projection-table FK MUST store BOTH components
    — surrogate ``id`` alone is insufficient because PG cannot route
    the FK lookup to the correct partition without the partition key.

    Args:
        observation_kind: VARCHAR(32) discriminator.  MUST be in
            ``OBSERVATION_KIND_VALUES``.  Cohort 4 only exercises
            ``'game_state'``; other kinds reserved for Cohorts 5-9.
        source_id: BIGINT FK into ``observation_source.id`` (slot 0075).
            ON DELETE RESTRICT — source registry is authoritative.
        canonical_primary_event_id: BIGINT FK into ``canonical_events.id``.
            **Renamed from canonical_event_id in V2.45 (slot 0084).**
            Denormalized "primary tag" — mirrors the ``link_kind =
            'primary'`` row in ``canonical_observation_event_links``
            (slot 0084 link table).  NULL allowed for cross-domain
            observations (weather, econ, news in future cohorts) that
            aren't tied to a canonical event.  ON DELETE SET NULL per
            V2.42 sub-amendment B + V2.43 Item 2 canonical-tier polarity.
        payload: dict containing the source observation payload at
            decision time.  MUST be JSON-serializable; the function
            canonicalizes via ``json.dumps(sort_keys=True, separators=
            (',', ':'))`` and computes the SHA-256 hash for the dedup
            key.  **V2.45 update:** the dict is NO LONGER stored on
            canonical_observations.payload (column dropped); only the
            hash is persisted (as the dedup key).  Per-kind projection
            tables hold the typed source data.
        event_occurred_at: TIMESTAMPTZ when the real-world event
            happened (e.g., when the play happened on the field).  NULL
            allowed for observations with no clear event time (econ
            prints aggregate over a window; news events are publication-
            time-only).
        source_published_at: TIMESTAMPTZ when the source emitted the
            observation (e.g., ESPN's payload publish time).  NOT NULL
            — every observation MUST have a source-side publish anchor
            for reconciler queries.  CHECK fires if more than 5 minutes
            ahead of ``ingested_at``.
        valid_until: TIMESTAMPTZ bitemporal "valid until".  NULL
            (default) = currently-valid (open-ended interval).
            Optional; the caller is generally OK leaving this NULL on
            initial append — a future row can SCD-2-style close the
            interval.

    Returns:
        Tuple of ``(id, ingested_at)`` — the composite PK projection.
        Callers MUST persist BOTH components if they need to FK-link a
        per-kind projection back to this row (composite FK invariant,
        V2.43 Item 3).

    Raises:
        ValueError: ``observation_kind`` not in
            ``OBSERVATION_KIND_VALUES`` (Pattern 73 SSOT real-guard;
            surfaced before SQL).
        TypeError: ``payload`` contains non-JSON-serializable values
            (raised at ``_compute_payload_hash`` time).
        psycopg2.errors.CheckViolation: clock-skew CHECK fired
            (``source_published_at`` more than 5 minutes ahead of
            ``ingested_at``) OR bitemporal validity CHECK fired
            (``valid_until < valid_at``).
        psycopg2.errors.UniqueViolation: dedup hit on
            ``(source_id, payload_hash, ingested_at)``.
        psycopg2.errors.ForeignKeyViolation: ``source_id`` absent from
            ``observation_source`` OR ``canonical_primary_event_id``
            absent from ``canonical_events``.

    Example:
        >>> from datetime import UTC, datetime
        >>> obs_id, ingested_at = append_observation_row(
        ...     observation_kind="game_state",
        ...     source_id=1,  # ESPN
        ...     canonical_primary_event_id=42,
        ...     payload={"home_score": 14, "away_score": 7, "quarter": 2},
        ...     event_occurred_at=datetime(2026, 5, 15, 19, 30, tzinfo=UTC),
        ...     source_published_at=datetime(2026, 5, 15, 19, 30, 5, tzinfo=UTC),
        ... )
        >>> # obs_id + ingested_at form the composite PK; persist BOTH
        >>> # if FK-linking from a per-kind projection table.

    Educational Note:
        The composite-key return shape is unusual for CRUD modules in
        this codebase, but mandatory for partitioned-parent writes.
        Future Cohort 9+ per-kind projection writers will look like:

            obs_id, obs_ingested_at = append_observation_row(...)
            insert_weather_observation(
                canonical_observation_id=obs_id,
                observation_ingested_at=obs_ingested_at,  # composite FK
                temperature_c=...,
                ...
            )

        Surrogate-id-only FK shapes will fail at PG layer (the FK
        lookup cannot route to the correct partition).

    Reference:
        - Migration 0078 (table DDL + 3 CHECK constraints + composite
          UNIQUE + composite PK + 5 indexes + BEFORE UPDATE trigger)
        - Migration 0084 (V2.45 redesign: payload column dropped,
          canonical_event_id renamed to canonical_primary_event_id,
          new canonical_observation_event_links table for multi-event
          tagging)
        - ``constants.py:OBSERVATION_KIND_VALUES``
        - ADR-118 V2.45 Items 4 + 8 (binding decisions for the V2.45
          redesign codified in slot 0084)
        - V2.43 Item 3 (composite-FK invariant for per-kind projections)
    """
    # Validate BEFORE opening the cursor so callers see a clear validation
    # message rather than a CheckViolation from psycopg2.  Pattern 73 SSOT
    # real-guard validation: the import of OBSERVATION_KIND_VALUES is USED
    # here in actual validation, NOT side-effect-only.
    if observation_kind not in OBSERVATION_KIND_VALUES:
        raise ValueError(
            f"observation_kind {observation_kind!r} not in canonical "
            f"OBSERVATION_KIND_VALUES {OBSERVATION_KIND_VALUES!r}; "
            "pattern 73 SSOT vocabulary violation"
        )

    # SHA-256 hash of canonicalized payload bytes is the dedup key.
    # V2.45: only the hash is persisted (payload column dropped); the
    # dict itself is consumed only to derive the hash.
    payload_hash = _compute_payload_hash(payload)
    # payload arg retained in signature for hash derivation but not
    # otherwise referenced post-V2.45.  Marker kept so static analysis
    # does not flag the parameter as unused.
    _ = payload

    query = """
        INSERT INTO canonical_observations (
            observation_kind, source_id, canonical_primary_event_id,
            payload_hash,
            event_occurred_at, source_published_at, valid_until
        ) VALUES (
            %s, %s, %s,
            %s,
            %s, %s, %s
        )
        RETURNING id, ingested_at
    """

    with get_cursor(commit=True) as cur:
        cur.execute(
            query,
            (
                observation_kind,
                source_id,
                canonical_primary_event_id,
                payload_hash,
                event_occurred_at,
                source_published_at,
                valid_until,
            ),
        )
        row = cur.fetchone()

    return cast("int", row["id"]), cast("datetime", row["ingested_at"])
