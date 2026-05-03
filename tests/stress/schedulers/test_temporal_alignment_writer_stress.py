"""Stress tests for temporal_alignment_writer.

Tests the quality classification function under high load (large batch sizes,
sustained call rates). Pure-function stress; no threading or scheduler state.

Reference:
    - TESTING_STRATEGY V3.9
    - Pattern 28 (CI-Safe Stress Testing — _is_ci skip for thread-based tests)
    - src/precog/schedulers/temporal_alignment_writer.py
    - #1019

Usage:
    pytest tests/stress/schedulers/test_temporal_alignment_writer_stress.py -v -m stress
"""

from __future__ import annotations

import os
import time
from decimal import Decimal

import pytest

pytest.skip(
    "V2.45 Migration 0084 redesigned temporal_alignment as pure-linkage table; "
    "temporal_alignment_writer references columns dropped under V2.45. "
    "Cohort 5+ rewrite per ADR-118 V2.45 Item 6 + issue #1141.",
    allow_module_level=True,
)

from precog.database.crud_ledger import VALID_ALIGNMENT_QUALITIES  # noqa: E402
from precog.schedulers.temporal_alignment_writer import _classify_quality  # noqa: E402

_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"


@pytest.mark.stress
class TestClassifyQualityStress:
    """High-volume stress tests for the pure classification function."""

    def test_high_volume_classification_no_degradation(self) -> None:
        """Classify 100K deltas; verify completion without errors and reasonable time."""
        deltas = [Decimal(str(i / 100)) for i in range(100_000)]

        start = time.perf_counter()
        results = [_classify_quality(d) for d in deltas]
        elapsed = time.perf_counter() - start

        assert len(results) == 100_000
        # 100K classifications should complete in well under 10 seconds even on
        # slow CI runners. Pure function, no I/O.
        assert elapsed < 10.0, f"100K classifications took {elapsed:.2f}s (expected < 10s)"

    def test_classification_handles_extreme_values(self) -> None:
        """Stress with extreme Decimal values (very large, very small, very precise)."""
        extreme_deltas = [
            Decimal("0"),
            Decimal("0.0000000001"),
            Decimal("999999999.999"),
            Decimal("1.000000000000000000000001"),
            Decimal("119.9999999999"),
            Decimal("120.0000000001"),
        ]

        for d in extreme_deltas:
            result = _classify_quality(d)
            assert result in VALID_ALIGNMENT_QUALITIES, (
                f"Classification of {d} returned unexpected value: {result}"
            )

    @pytest.mark.skipif(
        _is_ci,
        reason="Pattern 28: thread-based stress tests are CI-skipped (hang on 2-vCPU runners)",
    )
    def test_concurrent_classification_no_state_corruption(self) -> None:
        """Concurrent classification calls don't corrupt state (function is pure)."""
        from concurrent.futures import ThreadPoolExecutor

        deltas = [Decimal(str(i / 10)) for i in range(10_000)]

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(_classify_quality, deltas))

        assert len(results) == 10_000
        for r in results:
            assert r in VALID_ALIGNMENT_QUALITIES
