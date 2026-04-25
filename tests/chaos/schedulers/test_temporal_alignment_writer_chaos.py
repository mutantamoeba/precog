"""Chaos tests for temporal_alignment_writer.

Edge cases, boundary conditions, and unusual inputs for the quality
classification function and the find_unaligned_pairs DB query path
(with mocked DB returning malformed rows).

Reference:
    - TESTING_STRATEGY V3.9 (8-test-type discipline)
    - src/precog/schedulers/temporal_alignment_writer.py
    - #1019

Usage:
    pytest tests/chaos/schedulers/test_temporal_alignment_writer_chaos.py -v -m chaos
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.schedulers.temporal_alignment_writer import (
    _classify_quality,
    find_unaligned_pairs,
)


@pytest.mark.chaos
class TestClassifyQualityChaos:
    """Chaos: edge / unusual inputs for the pure classification function."""

    def test_exact_threshold_boundary_at_1s(self) -> None:
        """Delta exactly 1s is 'exact'; 1.000001s flips to 'good'."""
        assert _classify_quality(Decimal("1")) == "exact"
        assert _classify_quality(Decimal("1.000001")) == "good"

    def test_good_threshold_boundary_at_15s(self) -> None:
        """Delta exactly 15s is 'good'; 15.000001s flips to 'fair'."""
        assert _classify_quality(Decimal("15")) == "good"
        assert _classify_quality(Decimal("15.000001")) == "fair"

    def test_fair_threshold_boundary_at_60s(self) -> None:
        """Delta exactly 60s is 'fair'; 60.000001s flips to 'poor'."""
        assert _classify_quality(Decimal("60")) == "fair"
        assert _classify_quality(Decimal("60.000001")) == "poor"

    def test_poor_threshold_boundary_at_120s(self) -> None:
        """Delta exactly 120s is 'poor'; 120.000001s flips to 'stale'."""
        assert _classify_quality(Decimal("120")) == "poor"
        assert _classify_quality(Decimal("120.000001")) == "stale"

    def test_zero_delta_is_exact(self) -> None:
        """Perfectly synchronized poll (delta=0) is 'exact'."""
        assert _classify_quality(Decimal("0")) == "exact"

    def test_very_large_delta_is_stale(self) -> None:
        """Hour-scale delta is still classified (stale)."""
        assert _classify_quality(Decimal("3600")) == "stale"
        assert _classify_quality(Decimal("86400")) == "stale"  # 1 day


@pytest.mark.chaos
class TestFindUnalignedPairsChaos:
    """Chaos: error paths in find_unaligned_pairs (DB error simulation)."""

    @patch("precog.schedulers.temporal_alignment_writer.get_cursor")
    def test_db_error_during_fetch_propagates(self, mock_get_cursor: MagicMock) -> None:
        """If the cursor fetch raises, the exception propagates (no silent swallow)."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = RuntimeError("simulated DB error")
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(RuntimeError, match="simulated DB error"):
            find_unaligned_pairs()

    @patch("precog.schedulers.temporal_alignment_writer.get_cursor")
    def test_empty_result_returns_empty_list(self, mock_get_cursor: MagicMock) -> None:
        """No rows returned (writer caught up) returns empty list, not None or error."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = find_unaligned_pairs()
        assert result == []
        assert isinstance(result, list)
