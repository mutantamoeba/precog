"""CRUD operations for probability_models (SCD Type 2).

Post-Migration 0064 the ``probability_models`` table is SCD Type 2.
Status and metric updates are recorded as close-and-insert supersedes
rather than in-place UPDATEs.  This module is the thin CRUD layer the
``analytics.model_manager.ModelManager`` delegates to for those two
paths — eliminating the parallel in-place UPDATEs flagged in S62 as
Glokta P0-1 / Ripley #NEW-A.

Tables covered:
    - probability_models: versioned probability model configs + status/metrics

Mirrors the structure of ``crud_strategies.update_strategy_status`` +
``update_strategy_metrics`` — FOR UPDATE on the SELECT, NOW() snapshot
for temporal continuity, COALESCE carry-forward on unchanged fields,
and ``retry_on_scd_unique_conflict`` as an outer race guard.

Issue: #791
Epic: #745 (Schema Hardening Arc, Cohort C2c)
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, cast

from .connection import get_cursor
from .crud_shared import (
    DecimalEncoder,
    retry_on_scd_unique_conflict,
)

if TYPE_CHECKING:
    from decimal import Decimal

logger = logging.getLogger(__name__)


def update_model_status(
    model_id: int,
    new_status: str,
) -> bool:
    """
    Update probability_models.status via SCD Type 2 supersede.

    Post-Migration 0064, ``probability_models`` is SCD Type 2.  Status
    transitions are recorded as a close-and-insert supersede: the current
    row (matching ``model_id``) has ``row_current_ind`` flipped to FALSE
    and ``row_end_ts`` set to NOW(), then a new row is INSERTed with the
    same ``(model_name, model_version)`` natural key and the new status.
    The partial UNIQUE index
    ``idx_probability_models_name_version_current`` enforces
    at-most-one-current-version.

    Args:
        model_id: Model row ID.  Must reference a CURRENT row
            (``row_current_ind = TRUE``); superseding a historical row
            is not supported.
        new_status: New status ("draft", "testing", "active", "deprecated")

    Returns:
        bool: True if superseded, False if model not found or not current.
            The new SCD2 row gets a NEW ``model_id`` — callers should
            re-resolve via ``(model_name, model_version)`` if they need
            the id.

    Concurrency:
        Fetch SELECT uses ``FOR UPDATE`` to serialize concurrent callers
        against the same ``model_id``.  Mirror of the strategies
        supersede precedent (crud_strategies.update_strategy_status).

    Related:
        - Migration 0064 (adds SCD2 temporal columns to probability_models)
        - ``crud_strategies.update_strategy_status`` (sibling supersede)
        - ``crud_positions.update_position_price`` (FOR UPDATE precedent)
        - Glokta P0-1 / P0-2, Ripley #NEW-A / #NEW-B
    """
    # Fetch the current row with FOR UPDATE.  Every carry-forward column
    # must be SELECTed here or it is silently dropped on the new SCD2
    # row.  Round-2 remediation (S62 re-review):
    #   * activated_at / deactivated_at — audit-trail timestamps, sibling
    #     of the strategies P1-1 finding (Glokta N-1).
    #   * training_start_date / training_end_date / training_sample_size —
    #     training provenance (Glokta N-2).  These are the metadata
    #     describing which dataset the model was trained on and must
    #     survive every status/metric supersede unchanged.
    fetch_query = """
        SELECT model_name, model_version, model_class, domain, config,
               description, notes, created_by,
               activated_at, deactivated_at,
               training_start_date, training_end_date, training_sample_size,
               validation_calibration, validation_accuracy, validation_sample_size
        FROM probability_models
        WHERE model_id = %s AND row_current_ind = TRUE
        FOR UPDATE
    """

    close_query = """
        UPDATE probability_models
        SET row_current_ind = FALSE,
            row_end_ts = %s
        WHERE model_id = %s AND row_current_ind = TRUE
    """

    # INSERT column list must mirror the fetch carry-forward set plus
    # the caller-provided ``status`` and the SCD2 row-management columns.
    # The table's DEFAULT now() kicks in for ``created_at`` (same SCD2
    # "new row, new created_at" semantics as the strategies side).
    insert_query = """
        INSERT INTO probability_models (
            model_name, model_version, model_class, domain, config,
            description, status, created_by, notes,
            activated_at, deactivated_at,
            training_start_date, training_end_date, training_sample_size,
            validation_calibration, validation_accuracy, validation_sample_size,
            row_current_ind, row_start_ts, row_end_ts
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            TRUE, %s, NULL
        )
        RETURNING model_id
    """

    def _attempt_supersede() -> bool:
        with get_cursor(commit=True) as cur:
            cur.execute(fetch_query, (model_id,))
            current = cur.fetchone()
            if not current:
                return False

            cur.execute("SELECT NOW() AS ts")
            now_ts = cur.fetchone()["ts"]

            cur.execute(close_query, (now_ts, model_id))

            # Straight carry-forward for activated_at/deactivated_at
            # (probability_models' public API does not expose these as
            # caller-provided params — they are managed by the manager
            # layer via status transitions).  If that ever changes,
            # mirror the COALESCE pattern from
            # ``crud_strategies.update_strategy_status``.
            cur.execute(
                insert_query,
                (
                    current["model_name"],
                    current["model_version"],
                    current["model_class"],
                    current["domain"],
                    json.dumps(current["config"], cls=DecimalEncoder)
                    if not isinstance(current["config"], str)
                    else current["config"],
                    current["description"],
                    new_status,
                    current["created_by"],
                    current["notes"],
                    current["activated_at"],
                    current["deactivated_at"],
                    current["training_start_date"],
                    current["training_end_date"],
                    current["training_sample_size"],
                    current["validation_calibration"],
                    current["validation_accuracy"],
                    current["validation_sample_size"],
                    now_ts,
                ),
            )
            result = cur.fetchone()
            return result is not None

    return retry_on_scd_unique_conflict(
        _attempt_supersede,
        "idx_probability_models_name_version_current",
        business_key={"model_id": model_id, "new_status": new_status},
    )


def update_model_metrics(
    model_id: int,
    validation_calibration: Decimal | None = None,
    validation_accuracy: Decimal | None = None,
    validation_sample_size: int | None = None,
) -> bool:
    """
    Update probability_models validation metrics via SCD Type 2 supersede.

    Post-Migration 0064, metric updates are recorded as a close-and-insert
    supersede.  Metrics are MUTABLE across SCD2 versions (they accumulate
    as predictions are validated); config remains IMMUTABLE (guarded by
    ``trg_models_immutability``).

    Args:
        model_id: Model row ID.
        validation_calibration: Brier score / log loss (optional).
        validation_accuracy: Overall accuracy (optional).
        validation_sample_size: Number of validation samples (optional).

    Returns:
        bool: True if superseded, False if model not found.

    Raises:
        ValueError: If all three metric arguments are None.

    Related:
        - ``update_model_status`` — sibling supersede
        - Glokta P0-1 / Ripley #NEW-A: eliminates the parallel in-place
          UPDATE on metrics columns that bypassed SCD2.
    """
    if all(
        v is None for v in (validation_calibration, validation_accuracy, validation_sample_size)
    ):
        raise ValueError("At least one metric must be provided")

    # Same fetch/INSERT carry-forward surface as ``update_model_status``
    # plus ``status`` itself (unchanged on a metrics update).  Round-2
    # remediation mirrors the 5 newly-carried columns
    # (activated_at/deactivated_at + training_*) added to
    # ``update_model_status`` — silently dropping them on a metrics
    # supersede would bypass the N-1+N-2 fix on an adjacent path.
    fetch_query = """
        SELECT model_name, model_version, model_class, domain, config,
               description, status, notes, created_by,
               activated_at, deactivated_at,
               training_start_date, training_end_date, training_sample_size,
               validation_calibration, validation_accuracy, validation_sample_size
        FROM probability_models
        WHERE model_id = %s AND row_current_ind = TRUE
        FOR UPDATE
    """

    close_query = """
        UPDATE probability_models
        SET row_current_ind = FALSE,
            row_end_ts = %s
        WHERE model_id = %s AND row_current_ind = TRUE
    """

    insert_query = """
        INSERT INTO probability_models (
            model_name, model_version, model_class, domain, config,
            description, status, created_by, notes,
            activated_at, deactivated_at,
            training_start_date, training_end_date, training_sample_size,
            validation_calibration, validation_accuracy, validation_sample_size,
            row_current_ind, row_start_ts, row_end_ts
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            TRUE, %s, NULL
        )
        RETURNING model_id
    """

    def _attempt_supersede() -> bool:
        with get_cursor(commit=True) as cur:
            cur.execute(fetch_query, (model_id,))
            current = cur.fetchone()
            if not current:
                return False

            cur.execute("SELECT NOW() AS ts")
            now_ts = cur.fetchone()["ts"]

            cur.execute(close_query, (now_ts, model_id))

            cur.execute(
                insert_query,
                (
                    current["model_name"],
                    current["model_version"],
                    current["model_class"],
                    current["domain"],
                    json.dumps(current["config"], cls=DecimalEncoder)
                    if not isinstance(current["config"], str)
                    else current["config"],
                    current["description"],
                    current["status"],
                    current["created_by"],
                    current["notes"],
                    current["activated_at"],
                    current["deactivated_at"],
                    current["training_start_date"],
                    current["training_end_date"],
                    current["training_sample_size"],
                    validation_calibration
                    if validation_calibration is not None
                    else current["validation_calibration"],
                    validation_accuracy
                    if validation_accuracy is not None
                    else current["validation_accuracy"],
                    validation_sample_size
                    if validation_sample_size is not None
                    else current["validation_sample_size"],
                    now_ts,
                ),
            )
            result = cur.fetchone()
            return result is not None

    return retry_on_scd_unique_conflict(
        _attempt_supersede,
        "idx_probability_models_name_version_current",
        business_key={"model_id": model_id, "metric_update": True},
    )


def get_current_model(model_id: int) -> dict[str, Any] | None:
    """Fetch the CURRENT SCD2 row for a model by the CURRENT id.

    Helper used by ``ModelManager.update_status`` / ``update_metrics`` to
    re-resolve the returned row after supersede (the supersede allocates
    a NEW model_id; the caller needs to fetch the new row to return it).
    Looks up by ``(model_name, model_version)`` + ``row_current_ind =
    TRUE`` so callers holding a stale id can re-resolve after a
    concurrent supersede.

    Returns None if no current row matches — should never happen
    post-supersede but guards against race windows.
    """
    query = """
        SELECT model_id, model_name, model_version, model_class, domain,
               config, description, status,
               validation_calibration, validation_accuracy,
               validation_sample_size, created_at, created_by, notes
        FROM probability_models
        WHERE model_id = %s AND row_current_ind = TRUE
    """
    with get_cursor() as cur:
        cur.execute(query, (model_id,))
        return cast("dict[str, Any] | None", cur.fetchone())


def get_current_model_by_name_version(model_name: str, model_version: str) -> dict[str, Any] | None:
    """Fetch the CURRENT SCD2 row for a model by (name, version).

    Used by ``ModelManager`` methods to re-resolve after supersede
    (the new SCD2 row has a NEW model_id; the natural key is stable).
    """
    query = """
        SELECT model_id, model_name, model_version, model_class, domain,
               config, description, status,
               validation_calibration, validation_accuracy,
               validation_sample_size, created_at, created_by, notes
        FROM probability_models
        WHERE model_name = %s AND model_version = %s
          AND row_current_ind = TRUE
    """
    with get_cursor() as cur:
        cur.execute(query, (model_name, model_version))
        return cast("dict[str, Any] | None", cur.fetchone())
