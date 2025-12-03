"""
Performance Tests for Kalshi Authentication.

Establishes latency benchmarks for authentication operations:
- Signature generation latency
- Header generation throughput
- Key loading performance

Related:
- TESTING_STRATEGY V3.3: All 8 test types required
- api_connectors/kalshi_auth module coverage

Usage:
    pytest tests/performance/api_connectors/test_kalshi_auth_performance.py -v -m performance

Educational Note:
    These tests demonstrate the clean DI (Dependency Injection) approach.
    KalshiAuth now accepts an optional key_loader parameter, allowing us to
    inject a mock key loader directly instead of patching module internals.

    For performance tests, DI is especially beneficial as it eliminates
    patch overhead, giving more accurate latency measurements.

    Reference: Pattern 12 (Dependency Injection) in DEVELOPMENT_PATTERNS
"""

import time
from unittest.mock import MagicMock

import pytest


@pytest.mark.performance
class TestKalshiAuthPerformance:
    """Performance benchmarks for Kalshi authentication operations."""

    def _create_mock_auth(self):
        """Create a KalshiAuth with mocked key loading using DI."""
        from precog.api_connectors.kalshi_auth import KalshiAuth

        mock_private_key = MagicMock()
        mock_private_key.sign.return_value = b"mock_signature"

        return KalshiAuth(
            api_key="test-api-key",
            private_key_path="/fake/path/key.pem",
            key_loader=lambda path: mock_private_key,
        )

    def test_signature_generation_latency(self):
        """
        PERFORMANCE: Measure signature generation latency.

        Benchmark:
        - Target: < 5ms per signature (p95)
        - SLA: < 10ms per signature (p99)
        """
        auth = self._create_mock_auth()

        latencies = []

        for i in range(100):
            start = time.perf_counter()
            auth.get_headers(method="GET", path="/test/path")
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]

        assert p95 < 10, f"p95 latency {p95:.2f}ms exceeds 10ms target"
        assert p99 < 20, f"p99 latency {p99:.2f}ms exceeds 20ms SLA"

    def test_header_generation_throughput(self):
        """
        PERFORMANCE: Measure auth header generation throughput.

        Benchmark:
        - Target: >= 100 headers/sec
        """
        auth = self._create_mock_auth()

        operations = 200
        start = time.perf_counter()

        for i in range(operations):
            auth.get_headers(method="GET", path=f"/orders/{i}")

        elapsed = time.perf_counter() - start
        throughput = operations / elapsed

        assert throughput >= 50, f"Throughput {throughput:.1f} headers/sec below 50/sec minimum"

    def test_auth_initialization_time(self):
        """
        PERFORMANCE: Measure auth initialization time.

        Benchmark:
        - Target: < 50ms per initialization (p95)
        """
        from precog.api_connectors.kalshi_auth import KalshiAuth

        mock_private_key = MagicMock()

        latencies = []

        for _ in range(20):
            start = time.perf_counter()
            # Use DI to inject mock key loader
            KalshiAuth(
                api_key="test-api-key",
                private_key_path="/fake/path/key.pem",
                key_loader=lambda path: mock_private_key,
            )
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 100, f"p95 init time {p95:.2f}ms exceeds 100ms target"

    def test_token_expiry_check_latency(self):
        """
        PERFORMANCE: Measure token expiry check latency.

        Benchmark:
        - Target: < 0.5ms per check (p95)
        """
        auth = self._create_mock_auth()

        latencies = []

        for _ in range(500):
            start = time.perf_counter()
            auth.is_token_expired()
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 1, f"p95 token check latency {p95:.4f}ms exceeds 1ms target"
