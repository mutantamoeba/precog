"""Property-based tests for temporal_alignment_writer.

Hypothesis-driven invariants on the quality classification function. Catches
boundary conditions and verifies the classification is total (every Decimal
delta returns one of the 5 documented quality levels).

Reference:
    - TESTING_STRATEGY V3.9 (8-test-type discipline)
    - src/precog/schedulers/temporal_alignment_writer.py (_classify_quality)
    - #1019 (SKIP_TEST_TYPE_AUDIT bypass retirement — temporal_alignment_writer
      is the last failing module after crud_elo retirement)

Usage:
    pytest tests/property/schedulers/test_temporal_alignment_writer_properties.py -v -m property
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from precog.database.crud_ledger import VALID_ALIGNMENT_QUALITIES
from precog.schedulers.temporal_alignment_writer import _classify_quality


@pytest.mark.property
class TestClassifyQualityInvariants:
    """Hypothesis invariants on the _classify_quality pure function."""

    @given(
        delta=st.decimals(
            min_value=Decimal("0"),
            max_value=Decimal("100000"),
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=200)
    def test_classification_is_total(self, delta: Decimal) -> None:
        """Every non-negative Decimal delta returns one of the 5 quality levels."""
        result = _classify_quality(delta)
        assert result in VALID_ALIGNMENT_QUALITIES

    @given(
        delta_a=st.decimals(
            min_value=Decimal("0"), max_value=Decimal("1000"), allow_nan=False, allow_infinity=False
        ),
        delta_b=st.decimals(
            min_value=Decimal("0"), max_value=Decimal("1000"), allow_nan=False, allow_infinity=False
        ),
    )
    @settings(max_examples=200)
    def test_classification_is_monotonic(self, delta_a: Decimal, delta_b: Decimal) -> None:
        """Larger delta never produces a 'better' (smaller) quality category.

        Quality ordering: exact < good < fair < poor < stale. If delta_a < delta_b,
        then quality(a) is at most as bad as quality(b).
        """
        order = ["exact", "good", "fair", "poor", "stale"]
        if delta_a > delta_b:
            delta_a, delta_b = delta_b, delta_a
        # Now delta_a <= delta_b
        q_a = _classify_quality(delta_a)
        q_b = _classify_quality(delta_b)
        assert order.index(q_a) <= order.index(q_b), (
            f"Monotonicity violation: delta_a={delta_a} (quality={q_a}) "
            f"<= delta_b={delta_b} (quality={q_b}) but {q_a} > {q_b} in ordering"
        )

    @given(
        delta=st.decimals(
            min_value=Decimal("120.001"),
            max_value=Decimal("100000"),
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=50)
    def test_above_poor_threshold_is_stale(self, delta: Decimal) -> None:
        """Any delta strictly above the 120s POOR boundary is classified stale."""
        assert _classify_quality(delta) == "stale"

    @given(
        delta=st.decimals(
            min_value=Decimal("0"), max_value=Decimal("1"), allow_nan=False, allow_infinity=False
        )
    )
    @settings(max_examples=50)
    def test_at_or_below_exact_threshold_is_exact(self, delta: Decimal) -> None:
        """Deltas in [0, 1] inclusive are classified exact."""
        assert _classify_quality(delta) == "exact"
