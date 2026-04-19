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

from datetime import UTC, date, datetime
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
        """SCD2 supersede path: SELECT FOR UPDATE → NOW() → UPDATE close → INSERT new.

        Round-2 remediation: the fetch/INSERT now carries 5 additional
        columns — activated_at, deactivated_at (sibling of strategies P1-1,
        Glokta N-1) and training_start_date / training_end_date /
        training_sample_size (Glokta N-2).  The fixture populates all 5
        with non-NULL values so the carry-forward path is exercised (NULL
        values would pass even on a regression that dropped the column).
        """
        mock_cursor = MagicMock()
        now_ts = datetime(2026, 4, 18, 12, 0, 0, tzinfo=UTC)
        existing_activated = datetime(2026, 4, 1, 9, 0, 0, tzinfo=UTC)
        training_start = date(2025, 9, 1)
        training_end = date(2025, 12, 31)
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
                # N-1 carry-forward columns (non-NULL to exercise the path).
                "activated_at": existing_activated,
                "deactivated_at": None,
                # N-2 carry-forward columns.
                "training_start_date": training_start,
                "training_end_date": training_end,
                "training_sample_size": 4200,
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
        # N-1/N-2 regression guards: fetch must SELECT each new carry-forward column.
        for col in (
            "activated_at",
            "deactivated_at",
            "training_start_date",
            "training_end_date",
            "training_sample_size",
        ):
            assert col in fetch_sql, (
                f"Round-2 remediation: fetch must SELECT {col} "
                f"(N-1/N-2 carry-forward regression guard)"
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
        # N-1/N-2 regression guards: INSERT column list must include each new column.
        for col in (
            "activated_at",
            "deactivated_at",
            "training_start_date",
            "training_end_date",
            "training_sample_size",
        ):
            assert col in insert_sql, (
                f"Round-2 remediation: INSERT col list must include {col} "
                f"(N-1/N-2 carry-forward regression guard)"
            )

        # Pattern 43 grep #4: verify the INSERT VALUES tuple carries each
        # new column at the expected positional index.  Post-remediation
        # INSERT col order (18 caller-populated slots before the TRUE / NULL
        # literals, excluding row_current_ind/row_end_ts which are literals):
        #   0  model_name
        #   1  model_version
        #   2  model_class
        #   3  domain
        #   4  config
        #   5  description
        #   6  status               (caller-provided: new_status)
        #   7  created_by
        #   8  notes
        #   9  activated_at         (N-1 carry-forward)
        #   10 deactivated_at       (N-1 carry-forward)
        #   11 training_start_date  (N-2 carry-forward)
        #   12 training_end_date    (N-2 carry-forward)
        #   13 training_sample_size (N-2 carry-forward)
        #   14 validation_calibration
        #   15 validation_accuracy
        #   16 validation_sample_size
        #   17 row_start_ts         (now_ts)
        insert_params = mock_cursor.execute.call_args_list[3][0][1]
        assert insert_params[6] == "testing", "caller-provided status at index 6"
        assert insert_params[9] == existing_activated, (
            f"N-1: activated_at must carry forward. Got {insert_params[9]!r}"
        )
        assert insert_params[10] is None, "deactivated_at carries None from current row"
        assert insert_params[11] == training_start, (
            f"N-2: training_start_date must carry forward. Got {insert_params[11]!r}"
        )
        assert insert_params[12] == training_end, (
            f"N-2: training_end_date must carry forward. Got {insert_params[12]!r}"
        )
        assert insert_params[13] == 4200, (
            f"N-2: training_sample_size must carry forward. Got {insert_params[13]!r}"
        )

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
        """Metrics supersede: SELECT FOR UPDATE → NOW() → close → INSERT.

        Round-2 remediation: adds 5 new carry-forward columns
        (activated_at, deactivated_at, training_*) — fixture populates all
        with non-NULL values + positional assertions document the new
        index-shifted INSERT parameter order.
        """
        mock_cursor = MagicMock()
        now_ts = datetime(2026, 4, 18, 12, 0, 0, tzinfo=UTC)
        existing_activated = datetime(2026, 4, 1, 9, 0, 0, tzinfo=UTC)
        training_start = date(2025, 9, 1)
        training_end = date(2025, 12, 31)
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
                # N-1 carry-forward columns.
                "activated_at": existing_activated,
                "deactivated_at": None,
                # N-2 carry-forward columns.
                "training_start_date": training_start,
                "training_end_date": training_end,
                "training_sample_size": 4200,
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
        # N-1/N-2 regression guards on the fetch SELECT.
        for col in (
            "activated_at",
            "deactivated_at",
            "training_start_date",
            "training_end_date",
            "training_sample_size",
        ):
            assert col in fetch_sql, f"Round-2 remediation: metrics fetch must SELECT {col}"

        # Pattern 43 grep #4: INSERT carries forward status (from current row)
        # and the SPECIFIC metric COLUMNS updated.  Caller passed calibration
        # and sample_size but NOT accuracy — accuracy must be carried forward.
        insert_call = mock_cursor.execute.call_args_list[3]
        insert_params = insert_call[0][1]
        insert_sql = insert_call[0][0]
        for col in (
            "activated_at",
            "deactivated_at",
            "training_start_date",
            "training_end_date",
            "training_sample_size",
        ):
            assert col in insert_sql, (
                f"Round-2 remediation: metrics INSERT col list must include {col}"
            )

        # Post-remediation INSERT positional order (matches the SQL in
        # crud_probability_models.update_model_metrics):
        #   0  model_name
        #   1  model_version
        #   2  model_class
        #   3  domain
        #   4  config
        #   5  description
        #   6  status               (carry-forward)
        #   7  created_by
        #   8  notes
        #   9  activated_at         (N-1 carry-forward)
        #   10 deactivated_at       (N-1 carry-forward)
        #   11 training_start_date  (N-2 carry-forward)
        #   12 training_end_date    (N-2 carry-forward)
        #   13 training_sample_size (N-2 carry-forward)
        #   14 validation_calibration (caller-provided or carry-forward)
        #   15 validation_accuracy
        #   16 validation_sample_size
        #   17 row_start_ts
        assert insert_params[6] == "testing", "status must carry forward unchanged"
        assert insert_params[9] == existing_activated, (
            f"N-1: activated_at must carry forward on metrics supersede. Got {insert_params[9]!r}"
        )
        assert insert_params[10] is None, "deactivated_at carries current row's None"
        assert insert_params[11] == training_start, (
            f"N-2: training_start_date must carry forward. Got {insert_params[11]!r}"
        )
        assert insert_params[12] == training_end, (
            f"N-2: training_end_date must carry forward. Got {insert_params[12]!r}"
        )
        assert insert_params[13] == 4200, (
            f"N-2: training_sample_size must carry forward. Got {insert_params[13]!r}"
        )
        assert insert_params[14] == Decimal("0.05"), "caller calibration flows through"
        assert insert_params[15] is None, (
            "accuracy NOT provided; must carry forward the current row's None"
        )
        assert insert_params[16] == 1000, "caller sample_size flows through"

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
