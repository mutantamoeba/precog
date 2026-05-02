"""End-to-end tests for temporal_alignment_writer.

Exercises the full poll cycle (find_unaligned_pairs -> classify -> batch
insert) with mocked DB cursor. Verifies the writer's _poll_once integrates
the components correctly without requiring real PostgreSQL (integration
tests cover the DB-backed e2e path).

Reference:
    - TESTING_STRATEGY V3.9
    - src/precog/schedulers/temporal_alignment_writer.py
    - #1019

Usage:
    pytest tests/e2e/schedulers/test_temporal_alignment_writer_e2e.py -v -m e2e
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.schedulers.temporal_alignment_writer import (
    create_temporal_alignment_writer,
)


@pytest.mark.e2e
class TestTemporalAlignmentWriterE2E:
    """End-to-end poll cycle behavior with mocked DB."""

    @patch("precog.schedulers.temporal_alignment_writer.insert_temporal_alignment_batch")
    @patch("precog.schedulers.temporal_alignment_writer.get_cursor")
    def test_poll_cycle_processes_unaligned_pair(
        self, mock_get_cursor: MagicMock, mock_insert: MagicMock
    ) -> None:
        """Full poll cycle: find one unaligned pair, classify, insert."""
        now = datetime.now(tz=UTC)
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "market_snapshot_id": 1,
                "market_id": 10,
                "snapshot_time": now,
                "yes_ask_price": Decimal("0.55"),
                "no_ask_price": Decimal("0.45"),
                "spread": Decimal("0.10"),
                "volume": 100,
                "game_state_id": 5,
                "game_state_time": now,
                "game_status": "in_progress",
                "home_score": 7,
                "away_score": 3,
                "period": "Q2",
                "clock": "5:30",
                "game_id": 50,
                "time_delta_raw": Decimal("0.50"),
            }
        ]
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_insert.return_value = 1

        writer = create_temporal_alignment_writer()
        result = writer._poll_once()

        # Verify the full pipeline executed
        assert mock_get_cursor.called, "Should query for unaligned pairs"
        assert mock_insert.called, "Should insert the classified alignment"
        assert result.get("items_created", 0) >= 1, (
            f"Expected at least 1 alignment created, got {result!r}"
        )

    @patch("precog.schedulers.temporal_alignment_writer.insert_temporal_alignment_batch")
    @patch("precog.schedulers.temporal_alignment_writer.get_cursor")
    def test_poll_cycle_no_unaligned_pairs_no_insert(
        self, mock_get_cursor: MagicMock, mock_insert: MagicMock
    ) -> None:
        """When no unaligned pairs exist, no insert is attempted."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        writer = create_temporal_alignment_writer()
        writer._poll_once()

        mock_insert.assert_not_called()
