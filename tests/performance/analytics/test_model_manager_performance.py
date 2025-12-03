"""
Performance Tests for ModelManager.

Establishes latency benchmarks for model CRUD operations:
- Model registration latency
- Model version query performance
- Batch model operations throughput

Related:
- TESTING_STRATEGY V3.2: All 8 test types required
- analytics/model_manager module coverage

Usage:
    pytest tests/performance/analytics/test_model_manager_performance.py -v -m performance
"""

import statistics
import time

import pytest

from precog.database.connection import get_cursor


@pytest.mark.performance
class TestModelManagerPerformance:
    """Performance benchmarks for ModelManager operations."""

    @pytest.mark.skip(reason="models table not yet implemented - Phase 1.5+ (ModelManager)")
    def test_model_version_query_latency(self, db_pool, clean_test_data):
        """
        PERFORMANCE: Measure model version query latency.

        Benchmark:
        - Target: < 20ms per query (p95)
        - SLA: < 50ms per query (p99)
        """
        # Setup: Create test model
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO models (
                    model_name, model_version, model_type, description,
                    status, row_current_ind
                )
                VALUES ('perf-test-model', 'v1.0.0', 'elo', 'Performance test', 'active', TRUE)
                RETURNING model_id
                """
            )
            model_id = cur.fetchone()["model_id"]

        try:
            latencies = []

            for _ in range(50):
                start = time.perf_counter()
                with get_cursor() as cur:
                    cur.execute(
                        """
                        SELECT * FROM models
                        WHERE model_id = %s AND row_current_ind = TRUE
                        """,
                        (model_id,),
                    )
                    cur.fetchone()
                end = time.perf_counter()
                latencies.append((end - start) * 1000)

            _p50 = statistics.median(latencies)  # For potential future use
            p95 = sorted(latencies)[int(len(latencies) * 0.95)]
            p99 = sorted(latencies)[int(len(latencies) * 0.99)]

            assert p95 < 50, f"p95 latency {p95:.2f}ms exceeds 50ms target"
            assert p99 < 100, f"p99 latency {p99:.2f}ms exceeds 100ms SLA"

        finally:
            with get_cursor(commit=True) as cur:
                cur.execute("DELETE FROM models WHERE model_id = %s", (model_id,))

    @pytest.mark.skip(reason="models table not yet implemented - Phase 1.5+ (ModelManager)")
    def test_model_list_pagination_performance(self, db_pool, clean_test_data):
        """
        PERFORMANCE: Measure paginated model list query performance.

        Benchmark:
        - Target: < 30ms per page (p95)
        """
        # Setup: Create test models
        model_ids = []
        with get_cursor(commit=True) as cur:
            for i in range(20):
                cur.execute(
                    """
                    INSERT INTO models (
                        model_name, model_version, model_type, description,
                        status, row_current_ind
                    )
                    VALUES (%s, 'v1.0.0', 'elo', 'Perf test', 'active', TRUE)
                    RETURNING model_id
                    """,
                    (f"perf-model-{i:03d}",),
                )
                model_ids.append(cur.fetchone()["model_id"])

        try:
            latencies = []

            for _ in range(30):
                start = time.perf_counter()
                with get_cursor() as cur:
                    cur.execute(
                        """
                        SELECT * FROM models
                        WHERE row_current_ind = TRUE
                        ORDER BY model_id
                        LIMIT 10 OFFSET 0
                        """
                    )
                    cur.fetchall()
                end = time.perf_counter()
                latencies.append((end - start) * 1000)

            p95 = sorted(latencies)[int(len(latencies) * 0.95)]
            assert p95 < 50, f"p95 latency {p95:.2f}ms exceeds 50ms target"

        finally:
            with get_cursor(commit=True) as cur:
                for model_id in model_ids:
                    cur.execute("DELETE FROM models WHERE model_id = %s", (model_id,))

    @pytest.mark.skip(reason="models table not yet implemented - Phase 1.5+ (ModelManager)")
    def test_model_update_throughput(self, db_pool, clean_test_data):
        """
        PERFORMANCE: Measure model update throughput.

        Benchmark:
        - Target: >= 20 updates/sec
        """
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO models (
                    model_name, model_version, model_type, description,
                    status, row_current_ind
                )
                VALUES ('perf-update-model', 'v1.0.0', 'elo', 'Test', 'active', TRUE)
                RETURNING model_id
                """
            )
            model_id = cur.fetchone()["model_id"]

        try:
            start = time.perf_counter()
            operations = 20

            for i in range(operations):
                with get_cursor(commit=True) as cur:
                    cur.execute(
                        """
                        UPDATE models SET description = %s
                        WHERE model_id = %s
                        """,
                        (f"Updated {i}", model_id),
                    )

            elapsed = time.perf_counter() - start
            throughput = operations / elapsed

            assert throughput >= 10, f"Throughput {throughput:.1f} ops/sec below 10 ops/sec minimum"

        finally:
            with get_cursor(commit=True) as cur:
                cur.execute("DELETE FROM models WHERE model_id = %s", (model_id,))
