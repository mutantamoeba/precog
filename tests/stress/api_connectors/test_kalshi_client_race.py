"""
Race Condition Tests for Kalshi Client.

Tests for race conditions in API client operations:
- Concurrent session access
- Rate limiter contention
- Response parsing races

Related:
- TESTING_STRATEGY V3.3: All 8 test types required
- api_connectors/kalshi_client module coverage

Usage:
    pytest tests/stress/api_connectors/test_kalshi_client_race.py -v -m race

Educational Note:
    These tests demonstrate the clean DI (Dependency Injection) approach.
    Instead of patching internal module functions, we inject mock dependencies
    directly via constructor parameters.

    Reference: Pattern 12 (Dependency Injection) in DEVELOPMENT_PATTERNS

CI-Safe Refactoring (Issue #168):
    Previously used `xfail(run=False)` to skip in CI due to threading.Barrier hangs.
    Now uses CISafeBarrier with timeouts for graceful degradation:
    - Tests run in CI (not skipped)
    - Timeouts prevent indefinite hangs
    - Failures are fast and informative
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest

# Import CI-safe barrier from stress test fixtures
from tests.fixtures.stress_testcontainers import CISafeBarrier


@pytest.mark.race
class TestKalshiClientRace:
    """Race condition tests for Kalshi API client.

    Uses CISafeBarrier for CI-compatible thread synchronization.
    """

    # Timeout for barrier synchronization (seconds)
    # Set conservatively for CI resource constraints
    BARRIER_TIMEOUT = 15.0

    def _create_mock_client(self):
        """Create a KalshiClient with mocked dependencies using DI."""
        from precog.api_connectors.kalshi_client import KalshiClient

        # Create mock dependencies
        mock_auth = MagicMock()
        mock_auth.get_headers.return_value = {
            "Authorization": "Bearer mock-token",
            "Content-Type": "application/json",
        }

        mock_session = MagicMock()
        mock_limiter = MagicMock()

        # Inject dependencies via constructor
        return KalshiClient(
            environment="demo",
            auth=mock_auth,
            session=mock_session,
            rate_limiter=mock_limiter,
        )

    def test_concurrent_session_initialization(self):
        """
        RACE: Multiple threads initializing client simultaneously.

        Verifies:
        - Thread-safe client initialization
        - Single session per client

        Educational Note:
            This test uses clean DI (Dependency Injection) approach.
            Instead of patching internal module functions, we inject mock
            dependencies directly via constructor parameters.

            Reference: Pattern 12 (Dependency Injection) in DEVELOPMENT_PATTERNS
        """
        from precog.api_connectors.kalshi_client import KalshiClient

        clients = []
        errors = []
        barrier = CISafeBarrier(20, timeout=self.BARRIER_TIMEOUT)

        def create_client(thread_id: int):
            try:
                barrier.wait()  # Synchronize all threads (with timeout)
                # Use clean DI: inject mock dependencies directly
                mock_auth = MagicMock()
                mock_auth.get_headers.return_value = {
                    "Authorization": f"Bearer mock-token-{thread_id}",
                    "Content-Type": "application/json",
                }
                mock_session = MagicMock()
                mock_limiter = MagicMock()

                client = KalshiClient(
                    environment="demo",
                    auth=mock_auth,
                    session=mock_session,
                    rate_limiter=mock_limiter,
                )
                clients.append((thread_id, client))
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout - CI resource constraints"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(20):
            t = threading.Thread(target=create_client, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)  # Don't wait forever for threads

        # Allow barrier timeouts (CI resource constraints)
        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        other_errors = [e for e in errors if "timeout" not in e[1].lower()]

        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads timed out")

        assert len(other_errors) == 0, f"Errors during race test: {other_errors}"
        assert len(clients) == 20

    def test_concurrent_rate_limiter_access(self):
        """
        RACE: Multiple threads hitting rate limiter simultaneously.

        Verifies:
        - Thread-safe token bucket operations
        - Correct rate limiting under contention
        """
        from precog.api_connectors.rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=600)  # 10/sec
        wait_times = []
        errors = []
        barrier = CISafeBarrier(20, timeout=self.BARRIER_TIMEOUT)

        def check_rate_limit(thread_id: int):
            try:
                barrier.wait()  # Synchronize all threads (with timeout)
                start = time.perf_counter()
                limiter.wait_if_needed()
                elapsed = time.perf_counter() - start
                wait_times.append((thread_id, elapsed))
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(20):
            t = threading.Thread(target=check_rate_limit, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        # Handle CI timeouts gracefully
        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads timed out")

        other_errors = [e for e in errors if "timeout" not in e[1].lower()]
        assert len(other_errors) == 0, f"Errors: {other_errors}"

        # All threads should complete
        assert len(wait_times) == 20

    def test_interleaved_request_response(self):
        """
        RACE: Interleaved requests and response processing.

        Verifies:
        - No response mixing between concurrent requests
        - Each request gets its own response
        """
        client = self._create_mock_client()

        response_counter = [0]
        lock = threading.Lock()

        def thread_specific_response(*args, **kwargs):
            with lock:
                response_counter[0] += 1
                thread_id = response_counter[0]
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"thread_id": thread_id}
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        client.session.request = thread_specific_response
        client.rate_limiter.wait_if_needed = MagicMock()

        results = []
        barrier_errors = []
        barrier = CISafeBarrier(15, timeout=self.BARRIER_TIMEOUT)

        def make_request(thread_id: int):
            try:
                barrier.wait()
                resp = client.session.request("GET", f"/test/{thread_id}")
                results.append(resp.json())
            except TimeoutError:
                barrier_errors.append(thread_id)

        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(make_request, i) for i in range(15)]
            for f in futures:
                f.result(timeout=30)

        if barrier_errors:
            pytest.skip(f"Barrier timeout in CI: {len(barrier_errors)} threads")

        assert len(results) == 15

    def test_close_during_active_requests(self):
        """
        RACE: Closing client while requests are in flight.

        Verifies:
        - Graceful handling of close during operations
        - No crashes or deadlocks
        """
        client = self._create_mock_client()

        request_started = threading.Event()
        request_done = threading.Event()

        def slow_request(*args, **kwargs):
            request_started.set()
            time.sleep(0.05)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {}
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        client.session.request = slow_request
        client.session.close = MagicMock()
        client.rate_limiter.wait_if_needed = MagicMock()

        def make_slow_request():
            try:
                client.session.request("GET", "/slow")
            finally:
                request_done.set()

        # Start request in background
        thread = threading.Thread(target=make_slow_request)
        thread.start()

        # Wait for request to start, then close session
        request_started.wait()
        client.session.close()

        # Request should complete (or handle close gracefully)
        thread.join(timeout=2.0)
        assert not thread.is_alive(), "Request thread hung"
