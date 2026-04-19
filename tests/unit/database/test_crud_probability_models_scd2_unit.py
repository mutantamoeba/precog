"""Unit tests for ``crud_probability_models`` SCD2 supersede paths.

Migration 0064 put ``probability_models`` on SCD Type 2.  This module
is the CRUD-level supersede helper called by ``ModelManager`` — these
tests exercise it with stateful cursor mocks (Pattern 43) to verify
the SQL call sequence at the cursor level.

Pattern 43 4-grep checklist:
    1. Function name: ``update_model_status`` / ``update_model_metrics``
    2. ``fetchone.side_effect``: stateful — fetch → NOW() → INSERT RETURNING
    3. ``execute.call_count``: checked (fetch + NOW + close + insert = 4)
    4. ``call_args_list[0][0][0]`` contains FOR UPDATE

Issue: #791
Epic: #745 (Schema Hardening Arc, Cohort C2c)
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_probability_models import (
    update_model_metrics,
    update_model_status,
)


@pytest.mark.unit
class TestUpdateModelStatusSCD2Unit:
    """Unit tests for update_model_status SCD Type 2 supersede path."""

    @patch("precog.database.crud_probability_models.get_cursor")
    def test_update_model_status_supersedes_current_row(self, mock_get_cursor: MagicMock) -> None:
        """SCD2 supersede path: SELECT FOR UPDATE → NOW() → UPDATE close → INSERT new."""
        mock_cursor = MagicMock()
        now_ts = datetime(2026, 4, 18, 12, 0, 0, tzinfo=UTC)
        mock_cursor.fetchone.side_effect = [
            {
                "model_name": "elo_nfl",
                "model_version": "v1.0",
                "model_class": "elo",
                "domain": "nfl",
                "config": '{"k_factor": "32.0"}',
                "description": None,
                "notes": None,
                "created_by": None,
                "validation_calibration": None,
                "validation_accuracy": None,
                "validation_sample_size": None,
            },
            {"ts": now_ts},
            {"model_id": 201},  # new SCD2 row id
        ]
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_model_status(model_id=42, new_status="testing")

        assert result is True

        # Pattern 43 grep #3: fetch + NOW + close + insert = 4 executes.
        assert mock_cursor.execute.call_count == 4, (
            f"Expected 4 SQL executes; got {mock_cursor.execute.call_count}"
        )

        # Pattern 43 grep #4: fetch uses FOR UPDATE + row_current_ind filter.
        fetch_sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "FROM probability_models" in fetch_sql
        assert "row_current_ind = TRUE" in fetch_sql
        assert "FOR UPDATE" in fetch_sql, (
            "update_model_status fetch must use FOR UPDATE (Glokta P0-2 mirror)"
        )

        # NOW() snapshot + CLOSE-UPDATE + INSERT in sequence.
        now_sql = mock_cursor.execute.call_args_list[1][0][0]
        assert "NOW()" in now_sql

        close_sql = mock_cursor.execute.call_args_list[2][0][0]
        assert "UPDATE probability_models" in close_sql
        assert "row_current_ind = FALSE" in close_sql
        assert "row_end_ts = %s" in close_sql

        insert_sql = mock_cursor.execute.call_args_list[3][0][0]
        assert "INSERT INTO probability_models" in insert_sql
        assert "row_current_ind" in insert_sql
        assert "row_start_ts" in insert_sql

    @patch("precog.database.crud_probability_models.get_cursor")
    def test_update_model_status_returns_false_when_row_missing(
        self, mock_get_cursor: MagicMock
    ) -> None:
        """If no current row matches model_id, return False with NO supersede."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [None]
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_model_status(model_id=999, new_status="testing")

        assert result is False
        # Pattern 43 grep #3: only the SELECT ran, no writes.
        assert mock_cursor.execute.call_count == 1


@pytest.mark.unit
class TestUpdateModelMetricsSCD2Unit:
    """Unit tests for update_model_metrics SCD Type 2 supersede path."""

    @patch("precog.database.crud_probability_models.get_cursor")
    def test_update_model_metrics_supersedes_current_row(self, mock_get_cursor: MagicMock) -> None:
        """Metrics supersede: SELECT FOR UPDATE → NOW() → close → INSERT."""
        mock_cursor = MagicMock()
        now_ts = datetime(2026, 4, 18, 12, 0, 0, tzinfo=UTC)
        mock_cursor.fetchone.side_effect = [
            {
                "model_name": "elo_nfl",
                "model_version": "v1.0",
                "model_class": "elo",
                "domain": "nfl",
                "config": '{"k_factor": "32.0"}',
                "description": None,
                "status": "testing",
                "notes": None,
                "created_by": None,
                "validation_calibration": None,
                "validation_accuracy": None,
                "validation_sample_size": None,
            },
            {"ts": now_ts},
            {"model_id": 303},
        ]
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_model_metrics(
            model_id=42,
            validation_calibration=Decimal("0.05"),
            validation_sample_size=1000,
        )
        assert result is True

        assert mock_cursor.execute.call_count == 4

        fetch_sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "FOR UPDATE" in fetch_sql
        assert "row_current_ind = TRUE" in fetch_sql

        # Pattern 43 grep #4: INSERT carries forward status (from current row)
        # and the SPECIFIC metric COLUMNS updated.  Caller passed calibration
        # and sample_size but NOT accuracy — accuracy must be carried forward.
        insert_call = mock_cursor.execute.call_args_list[3]
        insert_params = insert_call[0][1]
        # INSERT positional order (from crud_probability_models.py):
        #   (model_name, model_version, model_class, domain, config,
        #    description, status, created_by, notes,
        #    validation_calibration, validation_accuracy, validation_sample_size,
        #    row_start_ts)
        # status at index 6, calibration at 9, accuracy at 10, sample_size at 11.
        assert insert_params[6] == "testing", "status must carry forward unchanged"
        assert insert_params[9] == Decimal("0.05"), "caller calibration flows through"
        assert insert_params[10] is None, (
            "accuracy NOT provided; must carry forward the current row's None"
        )
        assert insert_params[11] == 1000, "caller sample_size flows through"

    @patch("precog.database.crud_probability_models.get_cursor")
    def test_update_model_metrics_returns_false_when_row_missing(
        self, mock_get_cursor: MagicMock
    ) -> None:
        """Metrics supersede no-ops when model_id refers to a closed row."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [None]
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_model_metrics(model_id=999, validation_calibration=Decimal("0.05"))
        assert result is False
        assert mock_cursor.execute.call_count == 1

    def test_update_model_metrics_raises_on_no_metrics(self) -> None:
        """Caller must provide at least one metric."""
        with pytest.raises(ValueError, match="At least one metric"):
            update_model_metrics(model_id=42)
