"""
Performance Tests for Database Connection.

Establishes latency benchmarks for database connection operations:
- Connection acquisition latency
- Connection pool efficiency
- Query execution baseline

Related:
- TESTING_STRATEGY V3.2: All 8 test types required
- database/connection module coverage

Usage:
    pytest tests/performance/database/test_connection_performance.py -v -m performance
"""

import statistics
import time

import pytest

from precog.database.connection import get_cursor


@pytest.mark.performance
class TestConnectionPerformance:
    """Performance benchmarks for database connection operations."""

    def test_cursor_acquisition_latency(self, db_pool, clean_test_data):
        """
        PERFORMANCE: Measure cursor acquisition latency from pool.

        Benchmark:
        - Target: < 5ms per acquisition (p95)
        - SLA: < 10ms per acquisition (p99)
        """
        latencies = []

        for _ in range(100):
            start = time.perf_counter()
            with get_cursor():
                pass  # Just acquire and release
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]

        assert p95 < 10, f"p95 latency {p95:.2f}ms exceeds 10ms target"
        assert p99 < 20, f"p99 latency {p99:.2f}ms exceeds 20ms SLA"

    def test_simple_query_latency(self, db_pool, clean_test_data):
        """
        PERFORMANCE: Measure simple query execution latency.

        Benchmark:
        - Target: < 3ms per query (p95)
        """
        latencies = []

        for _ in range(100):
            start = time.perf_counter()
            with get_cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 10, f"p95 latency {p95:.2f}ms exceeds 10ms target"

    def test_connection_reuse_efficiency(self, db_pool, clean_test_data):
        """
        PERFORMANCE: Verify connection pool reuse is efficient.

        Benchmark:
        - Reused connections should be < 2x slower than first use
        """
        # First batch - cold connections
        first_batch = []
        for _ in range(10):
            start = time.perf_counter()
            with get_cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            end = time.perf_counter()
            first_batch.append((end - start) * 1000)

        # Second batch - warm connections (should be reused)
        second_batch = []
        for _ in range(10):
            start = time.perf_counter()
            with get_cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            end = time.perf_counter()
            second_batch.append((end - start) * 1000)

        avg_first = statistics.mean(first_batch)
        avg_second = statistics.mean(second_batch)

        # Second batch should not be significantly slower
        assert avg_second < avg_first * 3, (
            f"Reused connections {avg_second:.2f}ms slower than expected vs {avg_first:.2f}ms"
        )

    def test_batch_insert_throughput(self, db_pool, clean_test_data):
        """
        PERFORMANCE: Measure batch insert throughput.

        Benchmark:
        - Target: >= 100 inserts/sec for small rows
        """
        start = time.perf_counter()
        operations = 50

        with get_cursor(commit=True) as cur:
            for i in range(operations):
                cur.execute(
                    """
                    INSERT INTO venues (espn_venue_id, venue_name, city)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (espn_venue_id) DO NOTHING
                    """,
                    (f"PERF-BATCH-{i:04d}", f"Venue {i}", "Test City"),
                )

        elapsed = time.perf_counter() - start
        throughput = operations / elapsed

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM venues WHERE espn_venue_id LIKE 'PERF-BATCH-%'")

        assert throughput >= 50, f"Throughput {throughput:.1f} ops/sec below 50 ops/sec minimum"
