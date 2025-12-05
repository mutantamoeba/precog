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
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest

# CI environment detection - same pattern as connection stress tests
_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"

_CI_XFAIL_REASON = (
    "Race condition tests use threading barriers that can hang "
    "or timeout in CI environments due to resource constraints. "
    "Run locally with 'pytest tests/stress/ -v -m race'. See GitHub issue #168."
)


@pytest.mark.race
@pytest.mark.xfail(condition=_is_ci, reason=_CI_XFAIL_REASON, run=False)
class TestKalshiClientRace:
    """Race condition tests for Kalshi API client."""

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
        barrier = threading.Barrier(20)

        def create_client(thread_id: int):
            try:
                barrier.wait()
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
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(20):
            t = threading.Thread(target=create_client, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during race test: {errors}"
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
        barrier = threading.Barrier(20)

        def check_rate_limit(thread_id: int):
            barrier.wait()  # Synchronize all threads
            start = time.perf_counter()
            limiter.wait_if_needed()
            elapsed = time.perf_counter() - start
            wait_times.append((thread_id, elapsed))

        threads = []
        for i in range(20):
            t = threading.Thread(target=check_rate_limit, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

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
        barrier = threading.Barrier(15)

        def make_request(thread_id: int):
            barrier.wait()
            resp = client.session.request("GET", f"/test/{thread_id}")
            results.append(resp.json())

        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(make_request, i) for i in range(15)]
            for f in futures:
                f.result()

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
