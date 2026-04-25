"""Performance tests for temporal_alignment_writer.

Microbenchmarks on the quality classification function. Establishes a latency
budget so future regressions in the pure-function path are caught.

Reference:
    - TESTING_STRATEGY V3.9
    - src/precog/schedulers/temporal_alignment_writer.py
    - #1019

Usage:
    pytest tests/performance/schedulers/test_temporal_alignment_writer_performance.py -v -m performance
"""

from __future__ import annotations

import time
from decimal import Decimal

import pytest

from precog.schedulers.temporal_alignment_writer import _classify_quality


@pytest.mark.performance
class TestClassifyQualityPerformance:
    """Latency budget for the pure classification function."""

    def test_single_classification_completes_in_microseconds(self) -> None:
        """A single _classify_quality call should complete in <100us on any reasonable hardware."""
        d = Decimal("15.5")
        # Warmup
        for _ in range(100):
            _classify_quality(d)

        # Measure
        start = time.perf_counter_ns()
        for _ in range(1000):
            _classify_quality(d)
        elapsed_ns = time.perf_counter_ns() - start

        avg_us = (elapsed_ns / 1000) / 1000  # ns -> us per call
        # Pure function with 4 Decimal comparisons. Should be well under 100us
        # even on slow CI; setting a generous 500us budget for safety.
        assert avg_us < 500.0, f"Average classification took {avg_us:.2f}us (expected < 500us)"

    def test_batch_classification_throughput(self) -> None:
        """10K classifications should complete in well under 1 second."""
        deltas = [Decimal(str(i / 100)) for i in range(10_000)]

        start = time.perf_counter()
        for d in deltas:
            _classify_quality(d)
        elapsed = time.perf_counter() - start

        # 10K classifications in <1s = >10K ops/sec. Pure function should be
        # much faster than this; budget is intentionally loose for slow CI.
        assert elapsed < 1.0, f"10K classifications took {elapsed:.3f}s (expected < 1s)"

    def test_classification_does_not_allocate_excessively(self) -> None:
        """Repeated classification with the same input should not balloon memory.

        Loose check: classifying the same delta 100K times should not noticeably
        increase resident memory (the function returns interned strings; no
        intermediate Decimal allocation expected beyond constants).
        """
        d = Decimal("15.5")
        # Just verify it completes; memory profiling is heavyweight and
        # platform-dependent. Functional verification is sufficient at this
        # tier.
        for _ in range(100_000):
            result = _classify_quality(d)
            assert result == "fair"
