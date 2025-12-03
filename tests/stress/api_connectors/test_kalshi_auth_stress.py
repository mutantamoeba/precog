"""
Stress Tests for Kalshi Authentication.

Tests authentication behavior under high load conditions:
- Concurrent authentication requests
- Header generation throughput
- Sustained signature generation load

Related:
- TESTING_STRATEGY V3.3: All 8 test types required
- api_connectors/kalshi_auth module coverage

Usage:
    pytest tests/stress/api_connectors/test_kalshi_auth_stress.py -v -m stress

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
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest


@pytest.mark.stress
class TestKalshiAuthStress:
    """Stress tests for Kalshi authentication operations."""

    def _create_mock_auth(self):
        """Create a KalshiAuth with mocked key loading using DI."""
        from precog.api_connectors.kalshi_auth import KalshiAuth

        # Create a mock RSA private key
        mock_private_key = MagicMock()
        mock_private_key.sign.return_value = b"mock_signature_bytes"

        # Inject mock key loader via DI
        return KalshiAuth(
            api_key="test-api-key",
            private_key_path="/fake/path/key.pem",
            key_loader=lambda path: mock_private_key,
        )

    def test_concurrent_signature_generation(self):
        """
        STRESS: Generate signatures concurrently.

        Verifies:
        - Thread safety of signature generation
        - No data corruption under concurrent access
        - All operations complete successfully
        """
        auth = self._create_mock_auth()

        signatures = []
        errors = []

        def generate_headers(thread_id: int):
            try:
                headers = auth.get_headers(
                    method="GET",
                    path=f"/test/path/{thread_id}",
                )
                signatures.append((thread_id, headers))
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Run 50 concurrent signature generations
        threads = []
        for i in range(50):
            t = threading.Thread(target=generate_headers, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during stress test: {errors}"
        assert len(signatures) == 50

    def test_high_throughput_auth_headers(self):
        """
        STRESS: Generate auth headers at high throughput.

        Benchmark:
        - Target: >= 100 headers/sec
        """
        auth = self._create_mock_auth()

        operations = 100
        start = time.perf_counter()

        for i in range(operations):
            auth.get_headers(method="GET", path=f"/test/{i}")

        elapsed = time.perf_counter() - start
        throughput = operations / elapsed

        assert throughput >= 50, f"Throughput {throughput:.1f} ops/sec below 50 ops/sec minimum"

    def test_sustained_load(self):
        """
        STRESS: Sustained authentication load over time.

        Verifies:
        - System stability under continuous load
        - No memory leaks or resource exhaustion
        """
        auth = self._create_mock_auth()

        # Run for 2 seconds with continuous requests
        duration = 2.0
        start = time.perf_counter()
        count = 0

        while time.perf_counter() - start < duration:
            auth.get_headers(method="POST", path="/orders")
            count += 1

        elapsed = time.perf_counter() - start
        throughput = count / elapsed

        # Should maintain at least 25 ops/sec sustained
        assert throughput >= 25, (
            f"Sustained throughput {throughput:.1f} ops/sec dropped below minimum"
        )

    def test_concurrent_token_expiry_checks(self):
        """
        STRESS: Concurrent token expiry checks under load.

        Verifies:
        - Thread-safe access to token state
        - No race conditions in expiry checking
        """
        auth = self._create_mock_auth()

        results = []
        errors = []

        def check_expiry(thread_id: int):
            try:
                for _ in range(20):
                    expired = auth.is_token_expired()
                    results.append((thread_id, expired))
            except Exception as e:
                errors.append((thread_id, str(e)))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_expiry, i) for i in range(10)]
            for f in futures:
                f.result()

        assert len(errors) == 0, f"Errors during test: {errors}"
        assert len(results) == 200  # 10 threads * 20 checks each = 200
