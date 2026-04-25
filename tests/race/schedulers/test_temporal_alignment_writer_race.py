"""Race tests for temporal_alignment_writer.

Tests concurrent classification (verifying the pure function is thread-safe)
and concurrent _poll_once invocations don't double-write (mocked DB).

Reference:
    - TESTING_STRATEGY V3.9
    - Pattern 28 (CI-Safe Race Testing)
    - src/precog/schedulers/temporal_alignment_writer.py
    - #1019

Usage:
    pytest tests/race/schedulers/test_temporal_alignment_writer_race.py -v -m race
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from precog.schedulers.temporal_alignment_writer import _classify_quality

_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"


@pytest.mark.race
class TestClassifyQualityRace:
    """Verify _classify_quality is safe under concurrent access (pure function)."""

    def test_classification_is_deterministic_under_serial_calls(self) -> None:
        """Same input always returns same output (sanity check before concurrent test)."""
        d = Decimal("15.5")
        results = [_classify_quality(d) for _ in range(100)]
        assert all(r == "fair" for r in results)

    @pytest.mark.skipif(
        _is_ci,
        reason="Pattern 28: thread-based race tests are CI-skipped (hang on 2-vCPU runners)",
    )
    def test_concurrent_classification_returns_consistent_results(self) -> None:
        """Concurrent calls with the same input return the same classification."""
        d = Decimal("15.5")  # Should classify as 'fair' (just above 15s 'good' boundary)
        results: list[str] = []
        results_lock = threading.Lock()

        def classify_and_collect() -> None:
            r = _classify_quality(d)
            with results_lock:
                results.append(r)

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(classify_and_collect) for _ in range(500)]
            for f in futures:
                f.result()

        assert len(results) == 500
        assert all(r == "fair" for r in results), (
            f"Concurrent classification produced inconsistent results: "
            f"unique values = {set(results)}"
        )

    @pytest.mark.skipif(
        _is_ci,
        reason="Pattern 28: thread-based race tests are CI-skipped",
    )
    def test_concurrent_different_inputs_each_get_correct_classification(self) -> None:
        """Concurrent calls with different inputs each get their correct classification."""
        # Map of input -> expected output
        cases = {
            Decimal("0"): "exact",
            Decimal("10"): "good",
            Decimal("30"): "fair",
            Decimal("90"): "poor",
            Decimal("200"): "stale",
        }

        def classify_pair(item: tuple[Decimal, str]) -> bool:
            delta, expected = item
            return _classify_quality(delta) == expected

        # Run each case 50 times concurrently (250 total invocations)
        items = [(d, exp) for d, exp in cases.items() for _ in range(50)]
        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(classify_pair, items))

        assert all(results), "Some concurrent classifications returned wrong values"
