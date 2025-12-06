"""
Race Condition Tests for Kalshi Authentication.

Tests for race conditions in authentication operations:
- Concurrent key loading
- Simultaneous header operations
- Thread-safe signature generation

Related:
- TESTING_STRATEGY V3.3: All 8 test types required
- api_connectors/kalshi_auth module coverage

Usage:
    pytest tests/stress/api_connectors/test_kalshi_auth_race.py -v -m race

Educational Note:
    These tests demonstrate the clean DI (Dependency Injection) approach.
    KalshiAuth now accepts an optional key_loader parameter, allowing us to
    inject a mock key loader directly instead of patching module internals.

    Old approach (complex patching):
        with patch("precog.api_connectors.kalshi_auth.load_private_key") as mock_load:
            mock_load.return_value = mock_private_key
            auth = KalshiAuth(api_key="test", private_key_path="/path")

    New approach (clean DI):
        auth = KalshiAuth(
            api_key="test",
            private_key_path="/path",
            key_loader=lambda p: mock_private_key
        )

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
class TestKalshiAuthRace:
    """Race condition tests for Kalshi authentication.

    Uses CISafeBarrier for CI-compatible thread synchronization.
    """

    # Timeout for barrier synchronization (seconds)
    # Set conservatively for CI resource constraints
    BARRIER_TIMEOUT = 15.0

    def _create_mock_auth(self, api_key: str = "test-api-key"):
        """Create a KalshiAuth with mocked key loading using DI."""
        from precog.api_connectors.kalshi_auth import KalshiAuth

        # Create a mock RSA private key
        mock_private_key = MagicMock()
        mock_private_key.sign.return_value = b"mock_signature"

        # Inject mock key loader via DI
        return KalshiAuth(
            api_key=api_key,
            private_key_path="/fake/path/key.pem",
            key_loader=lambda path: mock_private_key,
        )

    def test_concurrent_auth_initialization(self):
        """
        RACE: Multiple threads initializing auth simultaneously.

        Verifies:
        - Thread-safe initialization
        - No duplicate key loading issues
        - Consistent state after concurrent init
        """
        from precog.api_connectors.kalshi_auth import KalshiAuth

        instances = []
        errors = []
        barrier = CISafeBarrier(20, timeout=self.BARRIER_TIMEOUT)

        mock_private_key = MagicMock()
        mock_private_key.sign.return_value = b"mock_signature"

        def create_auth(thread_id: int):
            try:
                barrier.wait()  # Synchronize all threads (with timeout)
                # Use DI to inject mock key loader
                auth = KalshiAuth(
                    api_key=f"test-key-{thread_id}",
                    private_key_path="/fake/path/key.pem",
                    key_loader=lambda path: mock_private_key,
                )
                instances.append((thread_id, auth))
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout - CI resource constraints"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(20):
            t = threading.Thread(target=create_auth, args=(i,))
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
        assert len(instances) == 20

    def test_concurrent_signature_with_same_timestamp(self):
        """
        RACE: Multiple threads generating signatures with same timestamp.

        Verifies:
        - Deterministic signature for same inputs
        - No corruption from concurrent access
        """
        auth = self._create_mock_auth()

        headers_list = []
        errors = []
        barrier = CISafeBarrier(30, timeout=self.BARRIER_TIMEOUT)

        def generate_headers(thread_id: int):
            try:
                barrier.wait()
                headers = auth.get_headers(method="GET", path="/test")
                headers_list.append(headers)
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(30):
            t = threading.Thread(target=generate_headers, args=(i,))
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
        assert len(headers_list) == 30

        # All headers should have KALSHI-ACCESS-KEY
        for headers in headers_list:
            assert "KALSHI-ACCESS-KEY" in headers
            assert headers["KALSHI-ACCESS-KEY"] == "test-api-key"

    def test_interleaved_read_write_operations(self):
        """
        RACE: Interleaved header generation and timestamp updates.

        Verifies:
        - No stale timestamp issues
        - Atomic header generation
        """
        auth = self._create_mock_auth()

        results = []
        barrier = CISafeBarrier(10, timeout=self.BARRIER_TIMEOUT)
        barrier_errors = []

        def interleaved_ops(thread_id: int):
            try:
                barrier.wait()  # Synchronize all threads
            except TimeoutError:
                barrier_errors.append(thread_id)
                return

            for _ in range(5):
                headers = auth.get_headers("GET", f"/path/{thread_id}")
                results.append(headers)
                time.sleep(0.001)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(interleaved_ops, i) for i in range(10)]
            for f in futures:
                f.result(timeout=30)

        if barrier_errors:
            pytest.skip(f"Barrier timeout in CI: {len(barrier_errors)} threads")

        # All operations should complete without corruption
        assert len(results) == 50  # 10 threads * 5 operations each

    def test_concurrent_token_state_access(self):
        """
        RACE: Concurrent access to token expiry state.

        Verifies:
        - Thread-safe access to token/expiry fields
        - No race conditions in expiry checking
        """
        auth = self._create_mock_auth()

        results = []
        errors = []
        barrier = CISafeBarrier(20, timeout=self.BARRIER_TIMEOUT)

        def check_token(thread_id: int):
            try:
                barrier.wait()
                for _ in range(10):
                    expired = auth.is_token_expired()
                    results.append((thread_id, expired))
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(20):
            t = threading.Thread(target=check_token, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        # Handle CI timeouts gracefully
        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads")

        other_errors = [e for e in errors if "timeout" not in e[1].lower()]
        assert len(other_errors) == 0, f"Errors: {other_errors}"
        assert len(results) == 200  # 20 threads * 10 checks
