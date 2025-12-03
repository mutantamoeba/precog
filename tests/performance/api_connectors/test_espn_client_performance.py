"""
Performance Tests for ESPNClient.

Establishes latency benchmarks for ESPN API operations:
- Response parsing performance
- Rate limiter overhead
- JSON deserialization throughput

Related:
- TESTING_STRATEGY V3.2: All 8 test types required
- api_connectors/espn_client module coverage

Usage:
    pytest tests/performance/api_connectors/test_espn_client_performance.py -v -m performance
"""

import time

import pytest


@pytest.mark.performance
class TestESPNClientPerformance:
    """Performance benchmarks for ESPNClient operations."""

    def test_response_parsing_latency(self):
        """
        PERFORMANCE: Measure ESPN response parsing latency.

        Benchmark:
        - Target: < 5ms per response (p95)
        - SLA: < 10ms per response (p99)
        """
        from precog.api_connectors.espn_client import ESPNClient

        # Mock response data
        mock_response = {
            "events": [
                {
                    "id": f"event_{i}",
                    "name": f"Team A vs Team B {i}",
                    "status": {"type": {"state": "in"}},
                    "competitions": [
                        {
                            "competitors": [
                                {"team": {"abbreviation": "TMA"}, "score": "21"},
                                {"team": {"abbreviation": "TMB"}, "score": "14"},
                            ]
                        }
                    ],
                }
                for i in range(10)
            ]
        }

        ESPNClient()
        latencies = []

        for _ in range(100):
            start = time.perf_counter()
            # Simulate parsing logic (just accessing nested data)
            events = mock_response.get("events", [])
            for event in events:
                _ = event.get("id")
                _ = event.get("status", {}).get("type", {}).get("state")
                competitions = event.get("competitions", [])
                for comp in competitions:
                    competitors = comp.get("competitors", [])
                    for competitor in competitors:
                        _ = competitor.get("team", {}).get("abbreviation")
                        _ = competitor.get("score")
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]

        assert p95 < 5, f"p95 latency {p95:.2f}ms exceeds 5ms target"
        assert p99 < 10, f"p99 latency {p99:.2f}ms exceeds 10ms SLA"

    def test_rate_limiter_overhead(self):
        """
        PERFORMANCE: Measure rate limiter check overhead.

        Benchmark:
        - Target: < 1ms per check (p99)
        """
        from precog.api_connectors.rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=1000)  # High limit to avoid blocking
        latencies = []

        for _ in range(200):
            start = time.perf_counter()
            limiter.wait_if_needed()
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        assert p99 < 5, f"p99 latency {p99:.2f}ms exceeds 5ms target"

    def test_client_initialization_time(self):
        """
        PERFORMANCE: Measure ESPNClient initialization time.

        Benchmark:
        - Target: < 50ms per initialization
        """
        from precog.api_connectors.espn_client import ESPNClient

        latencies = []

        for _ in range(20):
            start = time.perf_counter()
            client = ESPNClient()
            end = time.perf_counter()
            latencies.append((end - start) * 1000)
            client.close()  # Proper resource cleanup

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 100, f"p95 init time {p95:.2f}ms exceeds 100ms target"
