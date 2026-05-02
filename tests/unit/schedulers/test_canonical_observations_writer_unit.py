"""Unit tests for canonical_observations_writer skeleton — Cohort 4 slot 0078.

Cohort 4 ships the writer as a registration shell — ServiceSupervisor
wires it in, the feature-flag gate keeps it inert at production until
session 87 soak window opens, and the operator runbook documents the
activation procedure.  Cohort 5+ fills in the actual observation-
collection logic in ``_poll_once()``.

These tests verify the SKELETON contract:
    - Class-var triplet (SERVICE_KEY / HEALTH_COMPONENT / BREAKER_TYPE)
      is the metadata the supervisor reads at registration time.
    - ``_poll_once()`` is a deliberate no-op returning items_created=0
      (the Cohort 4 baseline; Cohort 5+ replaces the body).
    - Factory function returns a configured CanonicalObservationsWriter
      instance.

Reference:
    - ``src/precog/schedulers/canonical_observations_writer.py``
    - ``src/precog/schedulers/service_supervisor.py`` (SERVICE_TO_COMPONENT
      registration + SERVICE_FACTORIES)
    - ``memory/build_spec_0078_pm_memo.md`` § 5 (ServiceSupervisor
      registration spec)
"""

from __future__ import annotations

import pytest

from precog.schedulers.canonical_observations_writer import (
    CanonicalObservationsWriter,
    create_canonical_observations_writer,
)


@pytest.mark.unit
class TestCanonicalObservationsWriterClassVars:
    """Class-var triplet matches ServiceSupervisor registration expectations."""

    def test_service_key_is_canonical_observations_writer(self):
        """SERVICE_KEY matches the SERVICE_TO_COMPONENT registry key."""
        assert CanonicalObservationsWriter.SERVICE_KEY == "canonical_observations_writer"

    def test_health_component_is_canonical_observations_writer(self):
        """HEALTH_COMPONENT matches SERVICE_KEY (no separate mapping needed)."""
        assert CanonicalObservationsWriter.HEALTH_COMPONENT == "canonical_observations_writer"

    def test_breaker_type_is_data_stale(self):
        """BREAKER_TYPE is data_stale (parallel to temporal_alignment_writer rationale).

        Operationally-correct breaker for an observation-ingest service that
        has gone silent: consumer-facing alert is "the ingest pipeline is
        not producing fresh observations."  See writer module docstring for
        the full rationale.
        """
        assert CanonicalObservationsWriter.BREAKER_TYPE == "data_stale"


@pytest.mark.unit
class TestCanonicalObservationsWriterPollOnce:
    """Cohort 4 _poll_once() is a deliberate no-op (Cohort 5+ fills in the body)."""

    def test_poll_once_returns_zero_items_created(self):
        """Cohort 4 skeleton produces zero observations per cycle.

        When Cohort 5+ source-observation pipelines materialize, this
        body will read source data, canonicalize, and call
        ``append_observation_row()`` for each new observation.  Until
        then the writer heartbeats but produces zero observations —
        exactly the shape the feature-flag-gated deployment requires.
        """
        writer = CanonicalObservationsWriter(poll_interval=30)
        result = writer._poll_once()
        assert result == {"items_created": 0}

    def test_get_job_name_is_canonical_observations_writer(self):
        """_get_job_name returns the operator-facing job label."""
        writer = CanonicalObservationsWriter(poll_interval=30)
        assert writer._get_job_name() == "Canonical Observations Writer"


@pytest.mark.unit
class TestCreateCanonicalObservationsWriterFactory:
    """Factory function for ServiceSupervisor SERVICE_FACTORIES registry."""

    def test_factory_returns_writer_instance(self):
        """create_canonical_observations_writer returns CanonicalObservationsWriter."""
        result = create_canonical_observations_writer()
        assert isinstance(result, CanonicalObservationsWriter)

    def test_factory_uses_default_poll_interval(self):
        """Default poll_interval matches DEFAULT_POLL_INTERVAL class var."""
        result = create_canonical_observations_writer()
        # BasePoller stores poll_interval; access via the public attribute.
        assert result.poll_interval == CanonicalObservationsWriter.DEFAULT_POLL_INTERVAL

    def test_factory_accepts_custom_poll_interval(self):
        """poll_interval kwarg is forwarded to constructor."""
        result = create_canonical_observations_writer(poll_interval=60)
        assert result.poll_interval == 60


@pytest.mark.unit
class TestCanonicalObservationsWriterServiceSupervisorRegistration:
    """The class-var triplet is wired into ServiceSupervisor's registries.

    Mirrors slot 0073's Pattern 73 SSOT discipline: the registries are
    the canonical home for service registration; the unit test asserts
    the writer's class-vars match what the supervisor reads.
    """

    def test_writer_is_in_service_to_component_registry(self):
        """SERVICE_TO_COMPONENT contains canonical_observations_writer mapping."""
        from precog.schedulers.service_supervisor import SERVICE_TO_COMPONENT

        assert CanonicalObservationsWriter.SERVICE_KEY in SERVICE_TO_COMPONENT
        assert (
            SERVICE_TO_COMPONENT[CanonicalObservationsWriter.SERVICE_KEY]
            == CanonicalObservationsWriter.HEALTH_COMPONENT
        )

    def test_writer_is_in_component_to_breaker_type_registry(self):
        """COMPONENT_TO_BREAKER_TYPE contains the writer's breaker mapping."""
        from precog.schedulers.service_supervisor import COMPONENT_TO_BREAKER_TYPE

        assert CanonicalObservationsWriter.HEALTH_COMPONENT in COMPONENT_TO_BREAKER_TYPE
        assert (
            COMPONENT_TO_BREAKER_TYPE[CanonicalObservationsWriter.HEALTH_COMPONENT]
            == CanonicalObservationsWriter.BREAKER_TYPE
        )

    def test_writer_factory_is_in_service_factories_registry(self):
        """SERVICE_FACTORIES contains the writer factory."""
        from precog.schedulers.service_supervisor import SERVICE_FACTORIES

        assert "canonical_observations_writer" in SERVICE_FACTORIES
