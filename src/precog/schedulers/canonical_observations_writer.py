"""Canonical observations writer service (Cohort 4 skeleton).

Background service that will write canonical-tier observations into the
``canonical_observations`` partitioned parent table (slot 0078) via the
restricted CRUD function ``crud_canonical_observations.append_observation_row()``.

**Slot 0078 ships the SKELETON ONLY** — registration with
ServiceSupervisor + heartbeat surface + feature-flag gate.  The actual
observation-collection logic (read source observations from Kalshi /
ESPN / future weather feeds, transform to canonical-tier rows, append)
materializes in Cohort 5+ as the consumer pipeline forms.

Per build spec § 5 + § 9: the writer component is registered but feature
flag ``features.canonical_observations_writer.enabled`` stays ``false``
until session 87 soak window starts.  Production-Python-reader audit:
no production code path triggers this writer at slot-0078 deploy time.

Design rationale (build spec § 5 — register-skeleton-now-vs-later):

    The skeleton ships in slot 0078 (rather than a later "writer"-only
    slot) because:

        1. ServiceSupervisor registration tests (S69 + Pattern 43 scope)
           audit the registry's coverage — adding the component now
           closes the "registry has table-but-no-writer" gap that would
           otherwise look like a Pattern 73 SSOT drift.
        2. The operator runbook (``docs/operations/canonical_observations_
           runbook.md``) references the writer by service name; landing
           the runbook + the writer module in the same PR keeps the
           cross-references consistent.
        3. Feature-flag-gated registration is a zero-risk shape: the
           writer's ``_poll_once()`` is a no-op until Cohort 5+
           materializes the source-observation read path.  Risk surface
           in slot 0078 is bounded to "did the registration land?" —
           the same question every other ServiceSupervisor poller
           answers the same way.

    The "writer skeleton" lives here, not in ``crud_canonical_observations``.
    The CRUD module is a pure write-path function library; the writer
    is the long-running poller that calls it.  Slot 0078 keeps the
    separation clean so future Cohort 5+ writer logic doesn't blur the
    CRUD-vs-poller boundary.

Cohort 4 native metrics (build spec § 7 — ride existing JSONB surfaces):

    - ``canonical_observations_ingest_lag_seconds`` (p50/p95/p99 + last-
      value gauge) — measured per-row at writer-side; aggregated per
      heartbeat into ``scheduler_status.stats`` JSONB.  Cohort 4 baseline
      established during session 87+ soak.
    - ``canonical_observations_reconciliation_anomaly_count`` — written
      by the future reconciler module (separate slot/PR after writer
      soak per V2.43 micro-delta MD1), not by this writer.
    - ``canonical_observations_temporal_alignment_query_latency_p99`` —
      measured by the temporal_alignment writer (slot 0082+); Cohort 4
      forward-pointer only.

Reference:
    - Migration 0078 (``canonical_observations`` partitioned parent +
      composite PK + 5 indexes + dedup UNIQUE + 3 CHECKs + trigger)
    - ``src/precog/database/crud_canonical_observations.py``
      (``append_observation_row()`` — the only sanctioned write path)
    - ``docs/operations/canonical_observations_runbook.md`` (operator
      runbook for the writer component + partition lifecycle)
    - ``memory/build_spec_0078_pm_memo.md`` § 5 (ServiceSupervisor
      registration spec)
    - ADR-118 V2.43 Cohort 4
"""

from __future__ import annotations

import logging
from typing import ClassVar

from precog.schedulers.base_poller import BasePoller

logger = logging.getLogger(__name__)


class CanonicalObservationsWriter(BasePoller):
    """Background service skeleton for canonical_observations ingest.

    Cohort 4 ships the registration shell — ServiceSupervisor wires it
    in, the feature-flag gate keeps it inert at production until session
    87 soak window opens, and the operator runbook documents the
    activation procedure.  Cohort 5+ fills in the actual observation-
    collection logic in ``_poll_once()``.

    The class-var triplet (SERVICE_KEY / HEALTH_COMPONENT / BREAKER_TYPE)
    is the metadata the supervisor reads at registration time per the
    pattern documented in ``service_supervisor.py`` SERVICE_TO_COMPONENT
    registry.

    Cohort 4 ``_poll_once()`` is a deliberate no-op: the writer must be
    registrable + heartbeat-able for the operator runbook + integration
    tests to verify the wiring, but slot 0078 has no upstream source-
    observation pipeline to read from.  That pipeline lands Cohort 5+.
    """

    SERVICE_KEY: ClassVar[str] = "canonical_observations_writer"
    HEALTH_COMPONENT: ClassVar[str] = "canonical_observations_writer"
    # data_stale is the operationally-correct breaker for an observation-
    # ingest service that has gone silent.  Mirrors the temporal_alignment
    # writer's choice for the same operational reason (consumer-facing
    # alert: "the ingest pipeline is not producing fresh observations").
    BREAKER_TYPE: ClassVar[str] = "data_stale"

    MIN_POLL_INTERVAL: ClassVar[int] = 5
    # 30s baseline matches existing temporal_alignment_writer cadence; if
    # Cohort 5+ source-observation throughput requires a different cadence
    # the value tunes here.  Slot 0078 is no-op-per-cycle so the cadence
    # does not affect the system at deploy time.
    DEFAULT_POLL_INTERVAL: ClassVar[int] = 30

    def __init__(
        self,
        poll_interval: int | None = None,
    ) -> None:
        super().__init__(poll_interval=poll_interval)

    def _get_job_name(self) -> str:
        return "Canonical Observations Writer"

    def _poll_once(self) -> dict[str, int]:
        """Cohort 4 skeleton — no-op per cycle.

        The Cohort 5+ source-observation read path (Kalshi / ESPN /
        weather / etc.) will replace this body with the actual
        ingest loop.  Until then the writer heartbeats but produces
        zero observations — exactly the shape the feature-flag-gated
        deployment requires.

        Returns:
            Stats dict with ``items_created=0`` (Cohort 4 baseline).
            Future Cohort 5+ logic will return the per-cycle ingest
            count + lag-percentile metrics on the same dict.
        """
        # Slot 0078 deliberately produces zero observations.  When
        # Cohort 5+ source-observation pipelines materialize, this body
        # will read source data, canonicalize, and call
        # ``append_observation_row()`` for each new observation.  The
        # heartbeat itself is the Cohort 4 deliverable — it proves the
        # supervisor wiring works end-to-end.
        return {"items_created": 0}


def create_canonical_observations_writer(
    poll_interval: int = CanonicalObservationsWriter.DEFAULT_POLL_INTERVAL,
) -> CanonicalObservationsWriter:
    """Factory function for ServiceSupervisor registration.

    Mirrors the ``create_temporal_alignment_writer`` factory shape so the
    supervisor's SERVICE_FACTORIES registry has uniform construction
    semantics.
    """
    return CanonicalObservationsWriter(poll_interval=poll_interval)
