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
        #   [0] current row (lookup by strategy_id, FOR UPDATE locked)
        #   [1] NOW() ts row
        #   [2] INSERT RETURNING strategy_id (new supersede row id)
        #
        # Post-remediation: the current-row dict now includes
        # ``activated_at`` and ``deactivated_at`` (P1-1 carry-forward).
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
                "activated_at": None,
                "deactivated_at": None,
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
        # [0] SELECT ... FROM strategies WHERE strategy_id = %s AND row_current_ind = TRUE FOR UPDATE
        fetch_sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "FROM strategies" in fetch_sql
        assert "row_current_ind = TRUE" in fetch_sql, (
            "Lookup must filter by row_current_ind = TRUE to avoid superseding a historical row"
        )
        # P0-2 remediation: fetch MUST use FOR UPDATE to serialize concurrent
        # supersede callers (absent this, both callers see the same current
        # row and both INSERT, colliding on the partial UNIQUE index).
        assert "FOR UPDATE" in fetch_sql, (
            "Post-remediation: fetch SELECT must use FOR UPDATE (Glokta P0-2 / Ripley #NEW-B)"
        )
        # P1-1 remediation: fetch MUST include activated_at + deactivated_at
        # so the INSERT can COALESCE(caller, current_row) on each.
        assert "activated_at" in fetch_sql, (
            "Post-remediation: fetch must SELECT activated_at for P1-1 carry-forward"
        )
        assert "deactivated_at" in fetch_sql, (
            "Post-remediation: fetch must SELECT deactivated_at for P1-1 carry-forward"
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

    @patch("precog.database.crud_strategies.get_cursor")
    def test_update_strategy_status_carries_forward_activated_at(
        self, mock_get_cursor: MagicMock
    ) -> None:
        """P1-1: activated_at/deactivated_at are COALESCEd from the current row.

        Regression guard for Glokta P1-1 — the pre-remediation code
        passed the caller's (potentially None) value directly into the
        INSERT, so a deactivate call with ``deactivated_at=t2`` but no
        ``activated_at`` wiped the existing activated_at from the
        audit chain.  Post-remediation, activated_at must be the
        current row's value when the caller passes None.

        Pattern 43 grep #4: the INSERT call_args positional tuple carries
        the activated_at at a specific index — we assert on the tuple
        contents, not just the SQL string.
        """
        mock_cursor = MagicMock()
        now_ts = datetime(2026, 4, 18, 12, 0, 0, tzinfo=UTC)
        existing_activated = datetime(2026, 4, 1, 9, 0, 0, tzinfo=UTC)
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
                # Current row was ACTIVATED already — must carry forward.
                "activated_at": existing_activated,
                "deactivated_at": None,
            },
            {"ts": now_ts},
            {"strategy_id": 101},
        ]
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Caller passes ONLY deactivated_at (the "deactivate" gesture).
        # activated_at is None, so post-remediation it should be
        # carried forward from current["activated_at"].
        deactivated_ts = datetime(2026, 4, 18, 12, 0, 0, tzinfo=UTC)
        update_strategy_status(
            strategy_id=42,
            new_status="deprecated",
            deactivated_at=deactivated_ts,
        )

        # Pattern 43 grep #4: inspect INSERT call args (index 3).
        insert_call = mock_cursor.execute.call_args_list[3]
        insert_params = insert_call[0][1]
        # Mirror the INSERT's positional parameter ordering (the SQL is
        # in crud_strategies.py near the function definition):
        #   (platform_id, strategy_name, strategy_version, strategy_type,
        #    domain, config, status, activated_at, deactivated_at, notes,
        #    description, created_by, paper_trades_count, paper_roi,
        #    live_trades_count, live_roi, row_start_ts, updated_at)
        # => activated_at at index 7, deactivated_at at index 8.
        assert insert_params[7] == existing_activated, (
            f"P1-1: activated_at must carry forward when caller passes None. "
            f"Got {insert_params[7]!r}, expected {existing_activated!r}."
        )
        assert insert_params[8] == deactivated_ts, (
            f"deactivated_at must equal caller-provided value. "
            f"Got {insert_params[8]!r}, expected {deactivated_ts!r}."
        )


@pytest.mark.unit
class TestUpdateStrategyMetricsSCD2Unit:
    """Unit tests for update_strategy_metrics SCD Type 2 supersede path."""

    @patch("precog.database.crud_strategies.get_cursor")
    def test_update_strategy_metrics_supersedes_current_row(
        self, mock_get_cursor: MagicMock
    ) -> None:
        """Metrics supersede: SELECT FOR UPDATE → NOW() → close → INSERT.

        Pattern 43 4-grep:
          1. function name update_strategy_metrics (this test)
          2. fetchone.side_effect stateful (current row / NOW / INSERT)
          3. execute.call_count == 4
          4. call_args_list[0][0][0] contains FOR UPDATE
        """
        from precog.database.crud_strategies import update_strategy_metrics

        mock_cursor = MagicMock()
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
                "status": "active",
                "paper_trades_count": 10,
                "paper_roi": None,
                "live_trades_count": 0,
                "live_roi": None,
                "activated_at": None,
                "deactivated_at": None,
            },
            {"ts": now_ts},
            {"strategy_id": 202},
        ]
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        from decimal import Decimal

        result = update_strategy_metrics(
            strategy_id=42, paper_trades_count=15, paper_roi=Decimal("0.05")
        )
        assert result is True

        # Pattern 43 grep #3: fetch + NOW + close + insert
        assert mock_cursor.execute.call_count == 4, (
            f"Expected 4 executes, got {mock_cursor.execute.call_count}"
        )

        # Pattern 43 grep #4: fetch must use FOR UPDATE + filter current
        fetch_sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "FOR UPDATE" in fetch_sql
        assert "row_current_ind = TRUE" in fetch_sql

        # Close is UPDATE; INSERT carries forward status unchanged.
        close_sql = mock_cursor.execute.call_args_list[2][0][0]
        assert "UPDATE strategies" in close_sql
        assert "row_current_ind = FALSE" in close_sql

        insert_sql = mock_cursor.execute.call_args_list[3][0][0]
        assert "INSERT INTO strategies" in insert_sql

    @patch("precog.database.crud_strategies.get_cursor")
    def test_update_strategy_metrics_returns_false_when_row_missing(
        self, mock_get_cursor: MagicMock
    ) -> None:
        """Metrics supersede no-ops when strategy_id refers to a closed row."""
        from decimal import Decimal

        from precog.database.crud_strategies import update_strategy_metrics

        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [None]
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_strategy_metrics(strategy_id=999, paper_roi=Decimal("0.05"))
        assert result is False
        # Pattern 43 grep #3: only fetch executes, no writes.
        assert mock_cursor.execute.call_count == 1

    def test_update_strategy_metrics_raises_on_no_metrics(self) -> None:
        """Caller must provide at least one metric."""
        from precog.database.crud_strategies import update_strategy_metrics

        with pytest.raises(ValueError, match="At least one metric"):
            update_strategy_metrics(strategy_id=42)
