"""Unit tests for ``crud_strategies.update_strategy_status`` SCD2 supersede.

Migration 0064 converted ``update_strategy_status`` from an in-place
UPDATE into a close+INSERT supersede.  These tests use Pattern 43
(Mock Schema Fidelity) with stateful cursor mocks to verify the SQL
call sequence at the cursor level — pure-function mocks hide cascade
bugs in the supersede closure.

Pattern 43 4-grep checklist:
    1. Function name: ``update_strategy_status`` (covered by this file)
    2. ``fetchone.side_effect``: stateful — fetch → NOW() → INSERT RETURNING
    3. ``execute.call_count``: checked (fetch + NOW + close + insert = 4)
    4. ``call_args_list`` index: close at [2], insert at [3]

Issue: #791
Epic: #745 (Schema Hardening Arc, Cohort C2c)
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_strategies import update_strategy_status


@pytest.mark.unit
class TestUpdateStrategyStatusSCD2Unit:
    """Unit tests for update_strategy_status SCD Type 2 supersede path."""

    @patch("precog.database.crud_strategies.get_cursor")
    def test_update_strategy_status_supersedes_current_row(
        self, mock_get_cursor: MagicMock
    ) -> None:
        """SCD2 supersede path: SELECT → NOW() → UPDATE close → INSERT new.

        Stateful fetchone.side_effect mirrors the real cursor behaviour —
        a pure-function mock would return the same dict for every
        ``fetchone()`` call and hide the case where the supersede closure
        accidentally reuses the CURRENT-row dict for the INSERT
        RETURNING (cascading the old id into the caller).
        """
        mock_cursor = MagicMock()

        # fetchone returns, in order:
        #   [0] current row (lookup by strategy_id)
        #   [1] NOW() ts row
        #   [2] INSERT RETURNING strategy_id (new supersede row id)
        now_ts = datetime(2026, 4, 18, 12, 0, 0, tzinfo=UTC)
        mock_cursor.fetchone.side_effect = [
            {
                "strategy_name": "halftime_entry",
                "strategy_version": "v1.0",
                "strategy_type": "momentum",
                "platform_id": "kalshi",
                "domain": "nfl",
                "config": '{"min_lead": 7}',
                "notes": None,
                "description": None,
                "created_by": None,
                "paper_trades_count": 0,
                "paper_roi": None,
                "live_trades_count": 0,
                "live_roi": None,
            },
            {"ts": now_ts},
            {"strategy_id": 101},  # new SCD2 row id
        ]
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_strategy_status(strategy_id=42, new_status="testing")

        # Contract: returns True on successful supersede.
        assert result is True

        # Pattern 43 grep #3: execute.call_count must be exactly 4
        # (fetch current → NOW() snapshot → close-update → insert).
        # A regression that drops the NOW() snapshot or adds a
        # second UPDATE would change this count.
        assert mock_cursor.execute.call_count == 4, (
            f"Expected 4 SQL executes (fetch/NOW/close/insert); got "
            f"{mock_cursor.execute.call_count}"
        )

        # Pattern 43 grep #4: call_args_list index assertions.
        # [0] SELECT ... FROM strategies WHERE strategy_id = %s AND row_current_ind = TRUE
        fetch_sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "FROM strategies" in fetch_sql
        assert "row_current_ind = TRUE" in fetch_sql, (
            "Lookup must filter by row_current_ind = TRUE to avoid superseding a historical row"
        )

        # [1] SELECT NOW() AS ts — server-side timestamp for close/insert alignment.
        now_sql = mock_cursor.execute.call_args_list[1][0][0]
        assert "NOW()" in now_sql

        # [2] UPDATE close: SET row_current_ind = FALSE, row_end_ts = %s
        close_sql = mock_cursor.execute.call_args_list[2][0][0]
        assert "UPDATE strategies" in close_sql
        assert "row_current_ind = FALSE" in close_sql
        assert "row_end_ts = %s" in close_sql
        assert "row_current_ind = TRUE" in close_sql, (
            "Close must re-check row_current_ind = TRUE (race guard)"
        )

        # [3] INSERT new superseding row.
        insert_sql = mock_cursor.execute.call_args_list[3][0][0]
        assert "INSERT INTO strategies" in insert_sql
        assert "row_current_ind" in insert_sql
        assert "row_start_ts" in insert_sql
        assert "row_end_ts" in insert_sql
        # New row must be INSERTed as current (row_current_ind = TRUE).
        assert "TRUE" in insert_sql

    @patch("precog.database.crud_strategies.get_cursor")
    def test_update_strategy_status_returns_false_when_row_missing(
        self, mock_get_cursor: MagicMock
    ) -> None:
        """If no current row matches strategy_id, return False with NO supersede.

        This guards against the failure mode where a stale strategy_id
        is passed (either the id never existed, or it was already
        superseded by a sibling caller).  The function must short-circuit
        AFTER the fetch and BEFORE any write.  Pattern 43 grep #3
        (execute.call_count) catches this — a regression that forgets
        the early-return would show 4 executes instead of 1.
        """
        mock_cursor = MagicMock()
        # fetchone returns None on the first (and only) call — no
        # current row exists for this strategy_id.
        mock_cursor.fetchone.side_effect = [None]
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_strategy_status(strategy_id=999, new_status="testing")

        assert result is False

        # Pattern 43 grep #3: only ONE execute (the SELECT lookup).
        # If early-return is broken, this jumps to 4 and the test fails
        # loudly pointing at the bug.
        assert mock_cursor.execute.call_count == 1, (
            f"Expected 1 execute (fetch only) on missing row; got "
            f"{mock_cursor.execute.call_count} — early-return is broken"
        )

        # Pattern 43 grep #4: the one call is the SELECT lookup.
        fetch_sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "SELECT" in fetch_sql.upper()
        assert "FROM strategies" in fetch_sql
