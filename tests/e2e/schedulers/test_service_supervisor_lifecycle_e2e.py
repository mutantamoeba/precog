"""
End-to-End Tests for ServiceSupervisor Lifecycle (Credential-Independent).

These tests validate the supervisor's operational lifecycle WITHOUT requiring
any API credentials (Kalshi or ESPN). They run in CI and on any dev machine.

What makes these E2E and not integration?
    Integration tests (test_service_supervisor_integration.py) verify
    in-memory state: service.is_running(), supervisor.services["x"].healthy,
    supervisor.get_aggregate_metrics(). They do NOT verify:
    - Database writes (scheduler_status, system_health, circuit_breaker_events)
    - Cross-process IPC (the CLI `scheduler status` path)
    - Circuit breaker auto-trip from health check thread
    - Thread lifecycle across the full start->health->crash->restart->stop cycle

    These E2E tests verify all of the above with real DB, real threads,
    and real timing.

Test Classes:
    1. TestSupervisorLifecycleE2E - Full lifecycle with thread cleanup
    2. TestHealthCheckE2E - Health check loop writes to system_health table
    3. TestServiceCrashAndRestartE2E - Crash detection, DB state transitions
    4. TestCircuitBreakerAutoTripE2E - Auto-trip on service down
    5. TestAlertCallbackE2E - Alert callback fired from health thread
    6. TestDatabaseIPCE2E - scheduler_status populated for CLI IPC

Prerequisites:
    - PostgreSQL test database accessible (PRECOG_ENV=test)
    - No API credentials required

Run with:
    pytest tests/e2e/schedulers/test_service_supervisor_lifecycle_e2e.py -v -m e2e

Reference: ADR-100 (Service Supervisor Pattern)
Requirements: REQ-DATA-001, REQ-OBSERV-001, REQ-TEST-002
"""

import os
import socket
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from precog.database.connection import get_cursor
from precog.database.crud_schedulers import get_scheduler_status
from precog.database.crud_system import get_active_breakers, get_system_health
from precog.schedulers.service_supervisor import (
    Environment,
    RunnerConfig,
    ServiceConfig,
    ServiceSupervisor,
)

# Mark all tests in this module as E2E -- no skipif for credentials
pytestmark = [pytest.mark.e2e]


# =============================================================================
# Realistic Mock Service (copied from integration tests, extended for E2E)
# =============================================================================


class RealisticMockService:
    """
    A realistic mock service for E2E testing of supervisor lifecycle.

    Simulates a polling service with configurable failure modes. Unlike the
    integration test version, this one is tuned for faster E2E timing.

    Educational Note:
        E2E mocks serve a different purpose than integration mocks. They
        need to produce enough activity (polls, errors) to trigger the
        supervisor's DB-writing health check logic within short timeouts.
    """

    def __init__(
        self,
        name: str = "mock",
        poll_interval: float = 0.1,
        fail_after_polls: int | None = None,
        error_rate: float = 0.0,
    ) -> None:
        """
        Initialize realistic mock service.

        Args:
            name: Service identifier
            poll_interval: Simulated poll interval in seconds
            fail_after_polls: Stop running after this many polls (simulate crash)
            error_rate: Probability of incrementing error count per poll
        """
        self.name = name
        self.poll_interval = poll_interval
        self.fail_after_polls = fail_after_polls
        self.error_rate = error_rate

        self._running = False
        self._poll_count = 0
        self._error_count = 0
        self._poll_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the mock polling loop.

        Resets poll and error counts so that restarts behave like fresh starts.
        Without this, fail_after_polls would immediately re-trigger on restart
        because _poll_count persists from the previous run.
        """
        self._running = True
        self._poll_count = 0
        self._error_count = 0
        self._stop_event.clear()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def stop(self) -> None:
        """Stop the mock polling loop."""
        self._stop_event.set()
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=2)

    def is_running(self) -> bool:
        """Check if service is running."""
        return self._running

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "polls_completed": self._poll_count,
            "errors": self._error_count,
            "running": self._running,
        }

    def _poll_loop(self) -> None:
        """Simulated polling loop."""
        import random

        while not self._stop_event.is_set():
            self._stop_event.wait(self.poll_interval)
            if self._stop_event.is_set():
                break

            self._poll_count += 1

            # Simulate errors based on error_rate
            if random.random() < self.error_rate:
                self._error_count += 1

            # Simulate crash after certain polls
            if self.fail_after_polls and self._poll_count >= self.fail_after_polls:
                self._running = False
                break


# =============================================================================
# Shared Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _clean_db_tables():
    """Delete scheduler_status, system_health, and circuit_breaker_events before/after each test.

    E2E lifecycle tests create real supervisors that write to these tables.
    The startup guard detects stale scheduler_status entries and blocks
    subsequent tests. Health check threads may also write circuit breaker
    events that persist across tests.

    Educational Note:
        This is more aggressive than the integration test cleanup which only
        cleans scheduler_status. E2E tests exercise the full DB write path
        including system_health and circuit_breaker_events, so all three
        tables need cleanup.
    """

    def _purge():
        try:
            with get_cursor(commit=True) as cur:
                cur.execute("DELETE FROM scheduler_status")
                cur.execute("DELETE FROM system_health")
                # Only delete auto-tripped breakers (preserve manual ones)
                cur.execute("DELETE FROM circuit_breaker_events WHERE notes LIKE 'Auto-tripped:%'")
        except Exception:
            pass  # Tables may not exist in some test environments

    _purge()
    yield
    _purge()


@pytest.fixture
def e2e_config() -> RunnerConfig:
    """Create configuration optimized for E2E testing.

    Uses very short intervals so health checks and metrics fire quickly,
    keeping total test time manageable (< 30s per class).

    Educational Note:
        health_check_interval=1 means the health thread fires every 1s.
        For tests that need to observe a health check writing to DB, we
        sleep ~2s to guarantee at least one health check has completed.
    """
    return RunnerConfig(
        environment=Environment.DEVELOPMENT,
        log_level="DEBUG",
        log_dir=Path("/tmp/e2e_lifecycle_test_logs"),
        health_check_interval=1,
        metrics_interval=2,
    )


@pytest.fixture
def supervisor(e2e_config: RunnerConfig) -> ServiceSupervisor:
    """Create a supervisor instance for E2E testing.

    Yields the supervisor and ensures stop_all() is called on teardown,
    even if the test fails mid-execution (prevents thread leaks).
    """
    sup = ServiceSupervisor(e2e_config)
    yield sup
    # Defensive cleanup: stop if still running
    if sup.is_running:
        sup.stop_all()


# =============================================================================
# 1. Full Lifecycle E2E Tests
# =============================================================================


class TestSupervisorLifecycleE2E:
    """E2E tests for the full supervisor lifecycle: create -> start -> run -> stop.

    Why E2E?
        Integration tests verify in-memory state (service.is_running(), etc).
        These tests verify that the supervisor's DB writes (scheduler_status)
        and background threads (health, metrics) all start and stop cleanly
        as a coordinated whole. Thread leaks are a real production failure
        mode that only manifests under the full lifecycle.
    """

    def test_full_lifecycle_with_thread_cleanup(self, supervisor: ServiceSupervisor) -> None:
        """Verify create -> add -> start -> verify -> stop -> verify with thread cleanup."""
        # 1. Not running yet
        assert not supervisor.is_running

        # 2. Add service
        service = RealisticMockService(name="lifecycle", poll_interval=0.1)
        supervisor.add_service("lifecycle", service, ServiceConfig(name="Lifecycle Test"))
        assert "lifecycle" in supervisor.services

        # 3. Start
        supervisor.start_all()
        assert supervisor.is_running
        assert service.is_running()

        # 4. Let it run (accumulate some polls)
        time.sleep(0.5)
        assert service._poll_count > 0

        # 5. Record thread names before stop
        thread_names_before = {t.name for t in threading.enumerate()}
        assert "health-checker" in thread_names_before
        assert "metrics-reporter" in thread_names_before

        # 6. Stop
        supervisor.stop_all()
        assert not supervisor.is_running
        assert not service.is_running()

        # 7. Verify daemon threads stopped (give them a moment to join)
        time.sleep(0.5)
        thread_names_after = {t.name for t in threading.enumerate()}
        assert "health-checker" not in thread_names_after, (
            "health-checker thread should be cleaned up after stop_all()"
        )
        assert "metrics-reporter" not in thread_names_after, (
            "metrics-reporter thread should be cleaned up after stop_all()"
        )

    def test_multi_service_lifecycle(self, supervisor: ServiceSupervisor) -> None:
        """Verify lifecycle with multiple services, all start and stop cleanly."""
        services = []
        for i in range(3):
            svc = RealisticMockService(name=f"multi{i}", poll_interval=0.1)
            supervisor.add_service(f"multi{i}", svc, ServiceConfig(name=f"Multi {i}"))
            services.append(svc)

        supervisor.start_all()
        time.sleep(0.5)

        # All running and polling
        for svc in services:
            assert svc.is_running(), f"{svc.name} should be running"
            assert svc._poll_count > 0, f"{svc.name} should have polled"

        supervisor.stop_all()

        # All stopped
        for svc in services:
            assert not svc.is_running(), f"{svc.name} should be stopped"

    def test_graceful_shutdown_timing(self, supervisor: ServiceSupervisor) -> None:
        """Verify shutdown completes within a reasonable timeframe under load."""
        # 5 busy services
        for i in range(5):
            svc = RealisticMockService(name=f"busy{i}", poll_interval=0.05)
            supervisor.add_service(f"busy{i}", svc, ServiceConfig(name=f"Busy{i}"))

        supervisor.start_all()
        time.sleep(0.5)

        start = time.time()
        supervisor.stop_all()
        elapsed = time.time() - start

        assert elapsed < 10, f"Shutdown took {elapsed:.1f}s, expected < 10s"


# =============================================================================
# 2. Health Check E2E Tests
# =============================================================================


class TestHealthCheckE2E:
    """E2E tests for health check loop writing to system_health table.

    Why E2E?
        Integration tests verify that supervisor.services["x"].healthy is True.
        These tests verify that the health check thread actually writes
        'espn_api' -> 'healthy' into the system_health database table,
        which is the persistent state that the CLI reads for `scheduler status`.
        This DB write path cannot be verified without real DB + real threading.

    Key constraint:
        Only services named 'espn', 'kalshi_rest', or 'kalshi_ws' trigger
        system_health writes (via SERVICE_TO_COMPONENT mapping). Mock services
        with arbitrary names are silently skipped. Tests that need system_health
        writes use name='espn' for the mock service.
    """

    def test_health_check_writes_healthy_to_system_health(
        self, supervisor: ServiceSupervisor
    ) -> None:
        """Verify health check writes 'healthy' to system_health for espn_api."""
        # Name the mock 'espn' so SERVICE_TO_COMPONENT maps it to 'espn_api'
        service = RealisticMockService(name="espn", poll_interval=0.1)
        supervisor.add_service("espn", service, ServiceConfig(name="ESPN Mock"))

        supervisor.start_all()

        # Wait for at least one health check cycle (interval=1s, wait 2.5s)
        time.sleep(2.5)

        # Query system_health for espn_api component
        records = get_system_health(component="espn_api")

        assert len(records) > 0, (
            "system_health should have an entry for espn_api after health check"
        )
        assert records[0]["status"] == "healthy", (
            f"Expected 'healthy', got '{records[0]['status']}'"
        )
        assert records[0]["component"] == "espn_api"

        supervisor.stop_all()

    def test_health_check_skips_unmapped_services(self, supervisor: ServiceSupervisor) -> None:
        """Verify mock services not in SERVICE_TO_COMPONENT don't write system_health.

        Educational Note:
            This verifies the safe default: unknown service names are skipped
            in _update_system_health(). This is intentional -- future services
            should not crash the health check loop just because they lack a
            component mapping.
        """
        service = RealisticMockService(name="unknown", poll_interval=0.1)
        supervisor.add_service("unknown", service, ServiceConfig(name="Unknown Service"))

        supervisor.start_all()
        time.sleep(2.5)

        # Should NOT have written any system_health entries for this service
        # (unless other tests leaked; cleanup fixture handles that)
        records = get_system_health(component="unknown")
        assert len(records) == 0, "Unmapped service should not create system_health entries"

        supervisor.stop_all()

    def test_health_check_updates_on_repeated_cycles(self, supervisor: ServiceSupervisor) -> None:
        """Verify health check updates (not just inserts) on repeated cycles.

        Educational Note:
            system_health uses DELETE + INSERT per component per health check.
            This test verifies that multiple health checks don't create
            duplicate rows -- there should always be exactly one row per
            component.
        """
        service = RealisticMockService(name="espn", poll_interval=0.1)
        supervisor.add_service("espn", service, ServiceConfig(name="ESPN Mock"))

        supervisor.start_all()
        # Wait for at least 3 health check cycles
        time.sleep(4)

        records = get_system_health(component="espn_api")
        assert len(records) == 1, (
            f"Expected exactly 1 system_health row for espn_api, got {len(records)}"
        )

        supervisor.stop_all()


# =============================================================================
# 3. Service Crash and Restart E2E Tests
# =============================================================================


class TestServiceCrashAndRestartE2E:
    """E2E tests for crash detection, restart attempts, and DB state transitions.

    Why E2E?
        Integration tests check in-memory state.consecutive_failures. These
        tests verify the DB-visible state transitions: scheduler_status goes
        from 'running' -> 'failed' -> 'starting' -> 'running' (on successful
        restart) as the health check thread detects crashes and attempts
        restarts. The system_health table also transitions to 'down'.

    Key timing:
        fail_after_polls=2 with poll_interval=0.1 means crash at ~0.2s.
        health_check_interval=1 means detection at ~1s after crash.
        retry_delay=1 means restart attempt at ~1s after detection.
        Total: ~3-4s from start to restart attempt.
    """

    def test_crash_detected_and_system_health_goes_down(
        self, supervisor: ServiceSupervisor
    ) -> None:
        """Verify crash sets system_health to 'down' for the component."""
        service = RealisticMockService(name="espn", poll_interval=0.1, fail_after_polls=2)
        config = ServiceConfig(name="ESPN Crasher", max_retries=0, retry_delay=1)
        supervisor.add_service("espn", service, config)

        supervisor.start_all()

        # Wait for crash (0.2s) + health check detection (1s) + margin
        time.sleep(3)

        # system_health should show 'down' for espn_api
        records = get_system_health(component="espn_api")
        assert len(records) > 0, "system_health should have an espn_api entry"
        assert records[0]["status"] == "down", (
            f"Expected 'down' after crash, got '{records[0]['status']}'"
        )

        supervisor.stop_all()

    def test_restart_increments_restart_count(self, supervisor: ServiceSupervisor) -> None:
        """Verify restart_count increments after successful restart.

        Educational Note:
            The RealisticMockService with fail_after_polls will crash, but
            when restarted (start() called again), it resets its internal
            state and runs again. This simulates a transient failure where
            restart succeeds.
        """
        service = RealisticMockService(name="espn", poll_interval=0.1, fail_after_polls=3)
        config = ServiceConfig(name="ESPN Restarter", max_retries=3, retry_delay=1)
        supervisor.add_service("espn", service, config)

        supervisor.start_all()

        # Wait for crash + health check + restart delay + restart
        time.sleep(5)

        state = supervisor.services["espn"]
        assert state.restart_count > 0, f"Expected restart_count > 0, got {state.restart_count}"

        supervisor.stop_all()

    def test_scheduler_status_shows_failed_on_crash(self, supervisor: ServiceSupervisor) -> None:
        """Verify scheduler_status table reflects 'failed' after crash detection."""
        service = RealisticMockService(name="espn", poll_interval=0.1, fail_after_polls=2)
        config = ServiceConfig(name="ESPN Crasher", max_retries=0, retry_delay=1)
        supervisor.add_service("espn", service, config)

        supervisor.start_all()

        # Wait for crash + health check
        time.sleep(3)

        # Query scheduler_status for the espn service
        status_row = get_scheduler_status(supervisor.host_id, "espn")
        assert status_row is not None, "scheduler_status should have an espn entry"
        assert status_row["status"] == "failed", f"Expected 'failed', got '{status_row['status']}'"
        assert status_row["error_message"] is not None, (
            "error_message should be populated on failure"
        )

        supervisor.stop_all()


# =============================================================================
# 4. Circuit Breaker Auto-Trip E2E Tests
# =============================================================================


class TestCircuitBreakerAutoTripE2E:
    """E2E tests for automatic circuit breaker tripping on service down.

    Why E2E?
        The circuit breaker auto-trip happens inside _auto_trip_circuit_breaker(),
        called from _update_system_health(), called from _check_service_health(),
        called from the _health_check_loop() thread. This is a 4-level deep
        call chain that writes to circuit_breaker_events. Integration tests
        cannot verify this DB write without running the full health thread.

    Key mapping:
        Service name 'espn' -> component 'espn_api' -> breaker_type 'data_stale'.
        The breaker is only tripped when system_health transitions to 'down'
        and no active breaker of that type already exists.
    """

    def test_circuit_breaker_trips_on_permanent_failure(
        self, supervisor: ServiceSupervisor
    ) -> None:
        """Verify circuit breaker is created when service goes down permanently."""
        service = RealisticMockService(name="espn", poll_interval=0.1, fail_after_polls=2)
        config = ServiceConfig(name="ESPN Permanent Failure", max_retries=0)
        supervisor.add_service("espn", service, config)

        supervisor.start_all()

        # Wait for crash + health check + circuit breaker write
        time.sleep(3)

        # Query circuit_breaker_events for data_stale type
        breakers = get_active_breakers(breaker_type="data_stale")
        assert len(breakers) > 0, "Expected a 'data_stale' circuit breaker to be auto-tripped"

        breaker = breakers[0]
        assert breaker["breaker_type"] == "data_stale"
        assert "Auto-tripped" in (breaker.get("notes") or ""), (
            "Breaker notes should indicate auto-trip"
        )

        supervisor.stop_all()

    def test_duplicate_breaker_not_created(self, supervisor: ServiceSupervisor) -> None:
        """Verify repeated health checks don't create duplicate breakers.

        Educational Note:
            The _auto_trip_circuit_breaker() method checks get_active_breakers()
            before creating a new one. On the second health check that reports
            'down', the active breaker already exists so no duplicate is created.
        """
        service = RealisticMockService(name="espn", poll_interval=0.1, fail_after_polls=2)
        config = ServiceConfig(name="ESPN Dup Test", max_retries=0)
        supervisor.add_service("espn", service, config)

        supervisor.start_all()

        # Wait for multiple health checks after crash
        time.sleep(5)

        breakers = get_active_breakers(breaker_type="data_stale")
        assert len(breakers) == 1, (
            f"Expected exactly 1 active data_stale breaker, got {len(breakers)}"
        )

        supervisor.stop_all()

    def test_breaker_contains_component_details(self, supervisor: ServiceSupervisor) -> None:
        """Verify breaker trigger_value includes component name and reason."""
        service = RealisticMockService(name="espn", poll_interval=0.1, fail_after_polls=2)
        config = ServiceConfig(name="ESPN Details Test", max_retries=0)
        supervisor.add_service("espn", service, config)

        supervisor.start_all()
        time.sleep(3)

        breakers = get_active_breakers(breaker_type="data_stale")
        assert len(breakers) > 0

        trigger = breakers[0].get("trigger_value")
        assert trigger is not None, "trigger_value should be populated"
        # JSONB may come back as str depending on driver; parse if needed
        if isinstance(trigger, str):
            import json

            trigger = json.loads(trigger)
        assert isinstance(trigger, dict), f"trigger_value should be dict, got {type(trigger)}"
        assert trigger.get("component") == "espn_api", (
            f"Expected component='espn_api' in trigger_value, got {trigger}"
        )

        supervisor.stop_all()


# =============================================================================
# 5. Alert Callback E2E Tests
# =============================================================================


class TestAlertCallbackE2E:
    """E2E tests for alert callbacks triggered by the health check thread.

    Why E2E?
        Integration tests manually call _trigger_alert() or set up callbacks
        that may or may not fire within the test timing window. These E2E
        tests verify the full path: service crashes -> health check detects
        -> consecutive_failures exceeds max_retries -> alert triggered with
        correct service name and context. The alert fires from the health
        check thread, not the main thread.
    """

    def test_alert_fires_on_service_exhausting_retries(self, supervisor: ServiceSupervisor) -> None:
        """Verify alert callback is called when service exhausts max_retries.

        The alert fires when consecutive_failures > max_retries, with
        message indicating the service has given up.
        """
        received_alerts: list[tuple[str, str, dict[str, Any]]] = []
        alert_event = threading.Event()

        def alert_handler(name: str, message: str, context: dict[str, Any]) -> None:
            received_alerts.append((name, message, context))
            alert_event.set()

        supervisor.register_alert_callback(alert_handler)

        service = RealisticMockService(name="espn", poll_interval=0.1, fail_after_polls=2)
        # max_retries=0 means alert fires on first health check detection of crash
        config = ServiceConfig(name="ESPN Alerter", max_retries=0, retry_delay=1)
        supervisor.add_service("espn", service, config)

        supervisor.start_all()

        # Service crashes at ~0.2s. First health check at ~1s detects crash.
        # consecutive_failures=1 > max_retries=0, so alert fires immediately.
        got_alert = alert_event.wait(timeout=5)

        assert got_alert, "Alert callback should have been called within 5s"
        assert len(received_alerts) > 0, "Should have received at least one alert"

        name, message, context = received_alerts[0]
        assert name == "espn", f"Expected alert for 'espn', got '{name}'"
        assert "failed" in message.lower() or "giving up" in message.lower(), (
            f"Alert message should indicate failure: '{message}'"
        )
        assert "restart_count" in context, f"Alert context should include restart_count: {context}"

        supervisor.stop_all()

    def test_multiple_callbacks_all_receive_alert(self, supervisor: ServiceSupervisor) -> None:
        """Verify all registered callbacks receive the same alert."""
        events = [threading.Event() for _ in range(3)]
        received: list[list[tuple[str, str, dict[str, Any]]]] = [[] for _ in range(3)]

        for i in range(3):

            def make_handler(idx: int):
                def handler(name: str, msg: str, ctx: dict[str, Any]) -> None:
                    received[idx].append((name, msg, ctx))
                    events[idx].set()

                return handler

            supervisor.register_alert_callback(make_handler(i))

        service = RealisticMockService(name="espn", poll_interval=0.1, fail_after_polls=2)
        config = ServiceConfig(name="ESPN Multi-Callback", max_retries=0)
        supervisor.add_service("espn", service, config)

        supervisor.start_all()

        # Wait for all callbacks to fire
        for i, evt in enumerate(events):
            assert evt.wait(timeout=5), f"Callback {i} should have been called"

        supervisor.stop_all()

        # All three should have alerts
        for i in range(3):
            assert len(received[i]) > 0, f"Callback {i} should have received alerts"

    def test_alert_context_includes_meaningful_data(self, supervisor: ServiceSupervisor) -> None:
        """Verify alert context dict contains actionable information."""
        received_alerts: list[tuple[str, str, dict[str, Any]]] = []
        alert_event = threading.Event()

        def alert_handler(name: str, message: str, context: dict[str, Any]) -> None:
            received_alerts.append((name, message, context))
            alert_event.set()

        supervisor.register_alert_callback(alert_handler)

        service = RealisticMockService(name="espn", poll_interval=0.1, fail_after_polls=2)
        config = ServiceConfig(name="ESPN Context", max_retries=0)
        supervisor.add_service("espn", service, config)

        supervisor.start_all()
        alert_event.wait(timeout=5)
        supervisor.stop_all()

        assert len(received_alerts) > 0
        _name, _msg, context = received_alerts[0]

        # Context should have restart_count key (from the giving-up path)
        assert isinstance(context, dict), f"Context should be dict, got {type(context)}"
        assert "restart_count" in context, (
            f"Context should include 'restart_count', got keys: {list(context.keys())}"
        )


# =============================================================================
# 6. Database IPC E2E Tests
# =============================================================================


class TestDatabaseIPCE2E:
    """E2E tests for scheduler_status table -- enables CLI `scheduler status`.

    Why E2E?
        The scheduler_status table is the cross-process IPC mechanism. When
        `precog scheduler start` runs in process A, it writes to this table.
        When `precog scheduler status` runs in process B, it reads from it.
        Integration tests never verify the actual DB content -- only in-memory
        supervisor state. These tests query the DB directly to verify the
        same rows the CLI would read.
    """

    def test_scheduler_status_populated_on_start(self, supervisor: ServiceSupervisor) -> None:
        """Verify scheduler_status has correct entries after start_all()."""
        service = RealisticMockService(name="espn", poll_interval=0.1)
        supervisor.add_service("espn", service, ServiceConfig(name="ESPN IPC"))

        supervisor.start_all()
        # Small delay to let the _start_service DB write complete
        time.sleep(0.5)

        status = get_scheduler_status(supervisor.host_id, "espn")
        assert status is not None, "scheduler_status should have an espn entry"
        assert status["status"] == "running", f"Expected 'running', got '{status['status']}'"
        assert status["host_id"] == socket.gethostname()
        assert status["pid"] == os.getpid()

        supervisor.stop_all()

    def test_scheduler_status_cleared_after_stop(self, supervisor: ServiceSupervisor) -> None:
        """Verify scheduler_status rows are DELETED after stop_all() (Issue #755).

        Prior contract: stop_all() upserted status='stopped'. That left stale
        rows with fresh heartbeats, which the startup guard misread as
        concurrent instances and blocked restart.

        Current contract (per Issue #755): stop_all() DELETEs rows host-scoped.
        The table has no entry for this host after a clean shutdown, which
        lets the next start_all() proceed unambiguously.
        """
        service = RealisticMockService(name="espn", poll_interval=0.1)
        supervisor.add_service("espn", service, ServiceConfig(name="ESPN Stop"))

        supervisor.start_all()
        time.sleep(0.5)

        supervisor.stop_all()

        status = get_scheduler_status(supervisor.host_id, "espn")
        assert status is None, (
            f"Expected scheduler_status row to be deleted after stop_all(), got: {status}"
        )

    def test_scheduler_status_heartbeat_updates(self, supervisor: ServiceSupervisor) -> None:
        """Verify health check refreshes last_heartbeat in scheduler_status.

        Educational Note:
            The heartbeat is the 'lease renewal' that proves the service
            is still alive. If the heartbeat is older than the stale
            threshold, other processes consider the service crashed.
        """
        service = RealisticMockService(name="espn", poll_interval=0.1)
        supervisor.add_service("espn", service, ServiceConfig(name="ESPN HB"))

        supervisor.start_all()
        time.sleep(0.5)

        # Record initial heartbeat
        status_1 = get_scheduler_status(supervisor.host_id, "espn")
        assert status_1 is not None
        heartbeat_1 = status_1["last_heartbeat"]

        # Wait for at least one health check to update the heartbeat
        time.sleep(2)

        status_2 = get_scheduler_status(supervisor.host_id, "espn")
        assert status_2 is not None
        heartbeat_2 = status_2["last_heartbeat"]

        assert heartbeat_2 > heartbeat_1, (
            f"Heartbeat should advance after health check: {heartbeat_1} -> {heartbeat_2}"
        )

        supervisor.stop_all()

    def test_scheduler_status_includes_stats(self, supervisor: ServiceSupervisor) -> None:
        """Verify health check writes service stats to scheduler_status.

        The stats field is a JSONB column containing service-specific
        metrics (polls_completed, errors, etc).
        """
        service = RealisticMockService(name="espn", poll_interval=0.1)
        supervisor.add_service("espn", service, ServiceConfig(name="ESPN Stats"))

        supervisor.start_all()
        # Wait for health check to write stats
        time.sleep(2.5)

        status = get_scheduler_status(supervisor.host_id, "espn")
        assert status is not None

        stats = status.get("stats")
        assert stats is not None, "stats should be populated by health check"
        # Stats is stored as JSONB, may be dict or JSON string
        if isinstance(stats, str):
            import json

            stats = json.loads(stats)
        assert "polls_completed" in stats, f"stats should contain polls_completed, got: {stats}"
        assert stats["polls_completed"] > 0, "Should have completed polls by now"

        supervisor.stop_all()

    def test_multiple_services_in_scheduler_status(self, supervisor: ServiceSupervisor) -> None:
        """Verify each service gets its own row in scheduler_status."""
        svc1 = RealisticMockService(name="svc1", poll_interval=0.1)
        svc2 = RealisticMockService(name="svc2", poll_interval=0.1)
        supervisor.add_service("svc1", svc1, ServiceConfig(name="Svc 1"))
        supervisor.add_service("svc2", svc2, ServiceConfig(name="Svc 2"))

        supervisor.start_all()
        time.sleep(0.5)

        status_1 = get_scheduler_status(supervisor.host_id, "svc1")
        status_2 = get_scheduler_status(supervisor.host_id, "svc2")

        assert status_1 is not None, "svc1 should have a scheduler_status entry"
        assert status_2 is not None, "svc2 should have a scheduler_status entry"
        assert status_1["status"] == "running"
        assert status_2["status"] == "running"

        supervisor.stop_all()
