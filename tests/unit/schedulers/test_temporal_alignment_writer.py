"""Unit tests for temporal_alignment_writer.

Tests the quality classification logic and alignment record building.
DB interactions are mocked — real DB tests are in integration/.

Issue: #722
"""

from __future__ import annotations

from datetime import UTC
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.schedulers.temporal_alignment_writer import (
    TemporalAlignmentWriter,
    _classify_quality,
    create_temporal_alignment_writer,
    find_unaligned_pairs,
)


class TestClassifyQuality:
    """Verify quality thresholds are correct."""

    @pytest.mark.parametrize(
        ("delta", "expected"),
        [
            (Decimal("0"), "exact"),
            (Decimal("0.5"), "exact"),
            (Decimal("1"), "exact"),
            (Decimal("1.01"), "good"),
            (Decimal("10"), "good"),
            (Decimal("15"), "good"),
            (Decimal("15.01"), "fair"),
            (Decimal("30"), "fair"),
            (Decimal("60"), "fair"),
            (Decimal("60.01"), "poor"),
            (Decimal("90"), "poor"),
            (Decimal("120"), "poor"),
            (Decimal("120.01"), "stale"),
            (Decimal("300"), "stale"),
            (Decimal("9999"), "stale"),
        ],
    )
    def test_quality_classification(self, delta: Decimal, expected: str) -> None:
        assert _classify_quality(delta) == expected

    def test_boundaries_are_inclusive(self) -> None:
        """Boundary values (1, 15, 60, 120) belong to the better tier."""
        assert _classify_quality(Decimal("1")) == "exact"
        assert _classify_quality(Decimal("15")) == "good"
        assert _classify_quality(Decimal("60")) == "fair"
        assert _classify_quality(Decimal("120")) == "poor"


class TestFindUnalignedPairs:
    """Test the query-to-dict transformation in find_unaligned_pairs."""

    @patch("precog.schedulers.temporal_alignment_writer.get_cursor")
    def test_empty_result(self, mock_get_cursor: MagicMock) -> None:
        """No unaligned pairs returns empty list."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = find_unaligned_pairs()
        assert result == []

    @patch("precog.schedulers.temporal_alignment_writer.get_cursor")
    def test_transforms_rows_to_dicts(self, mock_get_cursor: MagicMock) -> None:
        """Rows from the query are transformed into alignment dicts."""
        from datetime import datetime

        now = datetime.now(tz=UTC)
        mock_row = {
            "market_snapshot_id": 42,
            "market_id": 10,
            "snapshot_time": now,
            "yes_ask_price": Decimal("0.6500"),
            "no_ask_price": Decimal("0.3800"),
            "spread": Decimal("0.0300"),
            "volume": 1500,
            "game_state_id": 99,
            "game_state_time": now,
            "game_status": "in",
            "home_score": 21,
            "away_score": 14,
            "period": "3",
            "clock": "8:42",
            "game_id": 5,
            "time_delta_raw": Decimal("2.34"),
        }

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [mock_row]
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = find_unaligned_pairs()
        assert len(result) == 1

        alignment = result[0]
        assert alignment["market_snapshot_id"] == 42
        assert alignment["game_state_id"] == 99
        assert alignment["time_delta_seconds"] == Decimal("2.34")
        assert alignment["alignment_quality"] == "good"  # 2.34s is within 15s
        assert alignment["yes_ask_price"] == Decimal("0.6500")
        assert alignment["game_id"] == 5
        assert alignment["home_score"] == 21
        assert alignment["clock"] == "8:42"

    @pytest.mark.parametrize(
        ("lookback", "limit"),
        [(0, 100), (-1, 100), (600, 0), (600, -5), (0, 0)],
    )
    def test_rejects_non_positive_params(self, lookback: int, limit: int) -> None:
        """Zero or negative lookback_seconds / batch_limit raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            find_unaligned_pairs(lookback_seconds=lookback, batch_limit=limit)

    @patch("precog.schedulers.temporal_alignment_writer.get_cursor")
    def test_null_prices_handled(self, mock_get_cursor: MagicMock) -> None:
        """NULL price fields remain None (not Decimal)."""
        from datetime import datetime

        now = datetime.now(tz=UTC)
        mock_row = {
            "market_snapshot_id": 1,
            "market_id": 1,
            "snapshot_time": now,
            "yes_ask_price": None,
            "no_ask_price": None,
            "spread": None,
            "volume": None,
            "game_state_id": 1,
            "game_state_time": now,
            "game_status": "pre",
            "home_score": 0,
            "away_score": 0,
            "period": "0",
            "clock": None,
            "game_id": 1,
            "time_delta_raw": Decimal("0.5"),
        }

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [mock_row]
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = find_unaligned_pairs()
        assert result[0]["yes_ask_price"] is None
        assert result[0]["no_ask_price"] is None
        assert result[0]["spread"] is None


class TestTemporalAlignmentWriter:
    """Test the writer service class."""

    def test_default_construction(self) -> None:
        writer = TemporalAlignmentWriter()
        assert writer.poll_interval == 30
        assert writer._lookback_seconds == 600
        assert writer._batch_limit == 1000

    def test_custom_construction(self) -> None:
        writer = TemporalAlignmentWriter(
            poll_interval=60,
            lookback_seconds=300,
            batch_limit=500,
        )
        assert writer.poll_interval == 60
        assert writer._lookback_seconds == 300
        assert writer._batch_limit == 500

    def test_min_poll_interval_enforced(self) -> None:
        with pytest.raises(ValueError, match="at least 5"):
            TemporalAlignmentWriter(poll_interval=2)

    def test_job_name(self) -> None:
        writer = TemporalAlignmentWriter()
        assert writer._get_job_name() == "Temporal Alignment Writer"

    def test_service_metadata(self) -> None:
        assert TemporalAlignmentWriter.SERVICE_KEY == "temporal_alignment"
        assert TemporalAlignmentWriter.HEALTH_COMPONENT == "temporal_alignment"
        assert TemporalAlignmentWriter.BREAKER_TYPE == "data_stale"

    @patch("precog.schedulers.temporal_alignment_writer.insert_temporal_alignment_batch")
    @patch("precog.schedulers.temporal_alignment_writer.find_unaligned_pairs")
    def test_poll_once_no_pairs(
        self,
        mock_find: MagicMock,
        mock_insert: MagicMock,
    ) -> None:
        """poll_once with no unaligned pairs inserts nothing."""
        mock_find.return_value = []
        writer = TemporalAlignmentWriter()
        result = writer._poll_once()
        assert result == {"items_created": 0}
        mock_insert.assert_not_called()

    @patch("precog.schedulers.temporal_alignment_writer.insert_temporal_alignment_batch")
    @patch("precog.schedulers.temporal_alignment_writer.find_unaligned_pairs")
    def test_poll_once_with_pairs(
        self,
        mock_find: MagicMock,
        mock_insert: MagicMock,
    ) -> None:
        """poll_once with pairs calls batch insert and returns count."""
        mock_find.return_value = [{"market_snapshot_id": 1}, {"market_snapshot_id": 2}]
        mock_insert.return_value = 2
        writer = TemporalAlignmentWriter()
        result = writer._poll_once()
        assert result == {"items_created": 2}
        mock_insert.assert_called_once()


class TestFactory:
    """Test the factory function."""

    def test_creates_writer(self) -> None:
        writer = create_temporal_alignment_writer()
        assert isinstance(writer, TemporalAlignmentWriter)
        assert writer.poll_interval == 30

    def test_custom_params(self) -> None:
        writer = create_temporal_alignment_writer(
            poll_interval=60,
            lookback_seconds=300,
            batch_limit=500,
        )
        assert writer.poll_interval == 60
        assert writer._lookback_seconds == 300
