"""
Unit Tests for Analytics CRUD Operations (Migration 0031).

Tests the 12 analytics CRUD functions: evaluation_runs (create, complete, get),
backtesting_runs (create, complete, get), predictions (create, resolve,
get_by_run, get_unresolved), and performance_metrics (upsert, get).

Validates Decimal enforcement, enum validation, optional parameter handling,
filtering, ordering, and upsert behavior.

Related:
- Migration 0031: analytics_tables
- ADR-002: Decimal Precision for All Financial Data
- migration_batch_plan_v1.md: Migration 0031 spec

Usage:
    pytest tests/unit/database/test_analytics_crud.py -v
    pytest tests/unit/database/test_analytics_crud.py -v -m unit
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_operations import (
    _VALID_ENTITY_TYPES,
    _VALID_RUN_STATUSES,
    _VALID_RUN_TYPES,
    complete_backtesting_run,
    complete_evaluation_run,
    create_backtesting_run,
    create_evaluation_run,
    create_prediction,
    get_backtesting_run,
    get_evaluation_run,
    get_performance_metrics,
    get_predictions_by_run,
    get_unresolved_predictions,
    resolve_prediction,
    upsert_performance_metric,
)

# =============================================================================
# HELPERS
# =============================================================================


def _mock_cursor_context(mock_get_cursor, mock_cursor=None):
    """Set up mock_get_cursor to return a context manager yielding mock_cursor."""
    if mock_cursor is None:
        mock_cursor = MagicMock()
    mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_cursor


# =============================================================================
# EVALUATION RUNS TESTS
# =============================================================================


@pytest.mark.unit
class TestCreateEvaluationRun:
    """Unit tests for create_evaluation_run function."""

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_evaluation_run_returns_surrogate_id(self, mock_get_cursor):
        """Test create_evaluation_run returns the integer surrogate PK."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = create_evaluation_run(run_type="model", model_id=1)

        assert result == 1

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_evaluation_run_validates_run_type(self, mock_get_cursor):
        """Test that invalid run_type values are rejected."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(ValueError, match="run_type must be one of"):
            create_evaluation_run(run_type="invalid")

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_evaluation_run_accepts_all_valid_run_types(self, mock_get_cursor):
        """Test that every valid run_type is accepted."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        for run_type in _VALID_RUN_TYPES:
            result = create_evaluation_run(run_type=run_type)
            assert result == 1

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_evaluation_run_with_config(self, mock_get_cursor):
        """Test create_evaluation_run with JSONB config."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 5}

        result = create_evaluation_run(
            run_type="model",
            model_id=1,
            config={"threshold": "0.05", "lookback_days": 30},
        )

        assert result == 5

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_evaluation_run_with_strategy_id(self, mock_get_cursor):
        """Test create_evaluation_run with strategy_id."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 3}

        result = create_evaluation_run(run_type="strategy", strategy_id=10)

        assert result == 3


@pytest.mark.unit
class TestCompleteEvaluationRun:
    """Unit tests for complete_evaluation_run function."""

    @patch("precog.database.crud_analytics.get_cursor")
    def test_complete_evaluation_run_returns_true(self, mock_get_cursor):
        """Test complete_evaluation_run returns True on success."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = complete_evaluation_run(run_id=1, status="completed")

        assert result is True

    @patch("precog.database.crud_analytics.get_cursor")
    def test_complete_evaluation_run_returns_false_when_not_found(self, mock_get_cursor):
        """Test complete_evaluation_run returns False when run_id not found."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = None

        result = complete_evaluation_run(run_id=999)

        assert result is False

    @patch("precog.database.crud_analytics.get_cursor")
    def test_complete_evaluation_run_validates_status(self, mock_get_cursor):
        """Test that invalid status values are rejected."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(ValueError, match="status must be one of"):
            complete_evaluation_run(run_id=1, status="invalid")

    @patch("precog.database.crud_analytics.get_cursor")
    def test_complete_evaluation_run_accepts_all_valid_statuses(self, mock_get_cursor):
        """Test that every valid status is accepted."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        for status in _VALID_RUN_STATUSES:
            result = complete_evaluation_run(run_id=1, status=status)
            assert result is True

    @patch("precog.database.crud_analytics.get_cursor")
    def test_complete_evaluation_run_with_summary(self, mock_get_cursor):
        """Test complete_evaluation_run with JSONB summary."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = complete_evaluation_run(
            run_id=1,
            summary={"accuracy": "0.82"},
            status="completed",
        )

        assert result is True

    @patch("precog.database.crud_analytics.get_cursor")
    def test_complete_evaluation_run_with_error(self, mock_get_cursor):
        """Test complete_evaluation_run with error_message for failed status."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = complete_evaluation_run(
            run_id=1,
            error_message="Model diverged during training",
            status="failed",
        )

        assert result is True


@pytest.mark.unit
class TestGetEvaluationRun:
    """Unit tests for get_evaluation_run function."""

    @patch("precog.database.crud_analytics.fetch_one")
    def test_get_evaluation_run_returns_dict(self, mock_fetch_one):
        """Test that a found run returns a dictionary."""
        mock_fetch_one.return_value = {"id": 1, "run_type": "model", "status": "completed"}

        result = get_evaluation_run(1)

        assert result == {"id": 1, "run_type": "model", "status": "completed"}

    @patch("precog.database.crud_analytics.fetch_one")
    def test_get_evaluation_run_returns_none_when_not_found(self, mock_fetch_one):
        """Test that a missing run returns None."""
        mock_fetch_one.return_value = None

        result = get_evaluation_run(999)

        assert result is None


# =============================================================================
# BACKTESTING RUNS TESTS
# =============================================================================


@pytest.mark.unit
class TestCreateBacktestingRun:
    """Unit tests for create_backtesting_run function."""

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_backtesting_run_returns_surrogate_id(self, mock_get_cursor):
        """Test create_backtesting_run returns the integer surrogate PK."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = create_backtesting_run(
            strategy_id=1,
            model_id=2,
            config={"min_edge": "0.05"},
            date_range_start=date(2025, 9, 1),
            date_range_end=date(2026, 1, 31),
        )

        assert result == 1

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_backtesting_run_with_none_ids(self, mock_get_cursor):
        """Test create_backtesting_run with None strategy/model IDs."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 2}

        result = create_backtesting_run(
            strategy_id=None,
            model_id=None,
            config={"type": "random_baseline"},
            date_range_start=date(2025, 9, 1),
            date_range_end=date(2026, 1, 31),
        )

        assert result == 2


@pytest.mark.unit
class TestCompleteBacktestingRun:
    """Unit tests for complete_backtesting_run function."""

    @patch("precog.database.crud_analytics.get_cursor")
    def test_complete_backtesting_run_returns_true(self, mock_get_cursor):
        """Test complete_backtesting_run returns True on success."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = complete_backtesting_run(
            run_id=1,
            total_trades=150,
            win_rate=Decimal("0.5800"),
            total_pnl=Decimal("125.5000"),
            status="completed",
        )

        assert result is True

    @patch("precog.database.crud_analytics.get_cursor")
    def test_complete_backtesting_run_returns_false_when_not_found(self, mock_get_cursor):
        """Test complete_backtesting_run returns False when run_id not found."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = None

        result = complete_backtesting_run(run_id=999)

        assert result is False

    @patch("precog.database.crud_analytics.get_cursor")
    def test_complete_backtesting_run_validates_status(self, mock_get_cursor):
        """Test that invalid status values are rejected."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(ValueError, match="status must be one of"):
            complete_backtesting_run(run_id=1, status="invalid")

    @patch("precog.database.crud_analytics.get_cursor")
    def test_complete_backtesting_run_validates_decimal_win_rate(self, mock_get_cursor):
        """Test that float values are rejected for win_rate."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(TypeError, match="win_rate must be Decimal"):
            complete_backtesting_run(run_id=1, win_rate=0.58)

    @patch("precog.database.crud_analytics.get_cursor")
    def test_complete_backtesting_run_validates_decimal_total_pnl(self, mock_get_cursor):
        """Test that float values are rejected for total_pnl."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(TypeError, match="total_pnl must be Decimal"):
            complete_backtesting_run(run_id=1, total_pnl=125.50)

    @patch("precog.database.crud_analytics.get_cursor")
    def test_complete_backtesting_run_validates_decimal_max_drawdown(self, mock_get_cursor):
        """Test that float values are rejected for max_drawdown."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(TypeError, match="max_drawdown must be Decimal"):
            complete_backtesting_run(run_id=1, max_drawdown=-45.20)

    @patch("precog.database.crud_analytics.get_cursor")
    def test_complete_backtesting_run_validates_decimal_sharpe_ratio(self, mock_get_cursor):
        """Test that float values are rejected for sharpe_ratio."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(TypeError, match="sharpe_ratio must be Decimal"):
            complete_backtesting_run(run_id=1, sharpe_ratio=1.32)

    @patch("precog.database.crud_analytics.get_cursor")
    def test_complete_backtesting_run_with_all_metrics(self, mock_get_cursor):
        """Test complete_backtesting_run with every metric provided."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = complete_backtesting_run(
            run_id=1,
            total_trades=150,
            win_rate=Decimal("0.5800"),
            total_pnl=Decimal("125.5000"),
            max_drawdown=Decimal("-45.2000"),
            sharpe_ratio=Decimal("1.3200"),
            results_detail={"by_sport": {"nfl": "0.62", "ncaaf": "0.54"}},
            status="completed",
        )

        assert result is True

    @patch("precog.database.crud_analytics.get_cursor")
    def test_complete_backtesting_run_with_error(self, mock_get_cursor):
        """Test complete_backtesting_run with error for failed status."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = complete_backtesting_run(
            run_id=1,
            error_message="Insufficient data for date range",
            status="failed",
        )

        assert result is True


@pytest.mark.unit
class TestGetBacktestingRun:
    """Unit tests for get_backtesting_run function."""

    @patch("precog.database.crud_analytics.fetch_one")
    def test_get_backtesting_run_returns_dict(self, mock_fetch_one):
        """Test that a found run returns a dictionary."""
        mock_fetch_one.return_value = {"id": 1, "total_trades": 150, "status": "completed"}

        result = get_backtesting_run(1)

        assert result["total_trades"] == 150

    @patch("precog.database.crud_analytics.fetch_one")
    def test_get_backtesting_run_returns_none_when_not_found(self, mock_fetch_one):
        """Test that a missing run returns None."""
        mock_fetch_one.return_value = None

        result = get_backtesting_run(999)

        assert result is None


# =============================================================================
# PREDICTIONS TESTS
# =============================================================================


@pytest.mark.unit
class TestCreatePrediction:
    """Unit tests for create_prediction function."""

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_prediction_returns_surrogate_id(self, mock_get_cursor):
        """Test create_prediction returns the integer surrogate PK."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = create_prediction(
            model_id=1,
            market_id=42,
            predicted_probability=Decimal("0.6500"),
        )

        assert result == 1

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_prediction_validates_decimal_probability(self, mock_get_cursor):
        """Test that float values are rejected for predicted_probability."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(TypeError, match="predicted_probability must be Decimal"):
            create_prediction(model_id=1, market_id=42, predicted_probability=0.65)

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_prediction_validates_probability_range_low(self, mock_get_cursor):
        """Test that predicted_probability below 0 is rejected."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(ValueError, match="predicted_probability must be between 0 and 1"):
            create_prediction(model_id=1, market_id=42, predicted_probability=Decimal("-0.0100"))

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_prediction_validates_probability_range_high(self, mock_get_cursor):
        """Test that predicted_probability above 1 is rejected."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(ValueError, match="predicted_probability must be between 0 and 1"):
            create_prediction(model_id=1, market_id=42, predicted_probability=Decimal("1.0100"))

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_prediction_validates_confidence_decimal(self, mock_get_cursor):
        """Test that float values are rejected for confidence."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(TypeError, match="confidence must be Decimal"):
            create_prediction(
                model_id=1,
                market_id=42,
                predicted_probability=Decimal("0.6500"),
                confidence=0.80,
            )

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_prediction_validates_confidence_range(self, mock_get_cursor):
        """Test that confidence out of [0,1] is rejected."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(ValueError, match="confidence must be between 0 and 1"):
            create_prediction(
                model_id=1,
                market_id=42,
                predicted_probability=Decimal("0.6500"),
                confidence=Decimal("1.5000"),
            )

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_prediction_validates_market_price_decimal(self, mock_get_cursor):
        """Test that float values are rejected for market_price_at_prediction."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(TypeError, match="market_price_at_prediction must be Decimal"):
            create_prediction(
                model_id=1,
                market_id=42,
                predicted_probability=Decimal("0.6500"),
                market_price_at_prediction=0.55,
            )

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_prediction_validates_market_price_range(self, mock_get_cursor):
        """Test that market_price_at_prediction out of [0,1] is rejected."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(ValueError, match="market_price_at_prediction must be between 0 and 1"):
            create_prediction(
                model_id=1,
                market_id=42,
                predicted_probability=Decimal("0.6500"),
                market_price_at_prediction=Decimal("1.5000"),
            )

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_prediction_validates_edge_decimal(self, mock_get_cursor):
        """Test that float values are rejected for edge."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(TypeError, match="edge must be Decimal"):
            create_prediction(
                model_id=1,
                market_id=42,
                predicted_probability=Decimal("0.6500"),
                edge=0.10,
            )

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_prediction_with_all_optional_fields(self, mock_get_cursor):
        """Test create_prediction with every optional parameter provided."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 99}

        result = create_prediction(
            model_id=1,
            market_id=42,
            predicted_probability=Decimal("0.6500"),
            confidence=Decimal("0.8000"),
            market_price_at_prediction=Decimal("0.5500"),
            edge=Decimal("0.1000"),
            evaluation_run_id=5,
            event_id=10,
        )

        assert result == 99

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_prediction_allows_boundary_values(self, mock_get_cursor):
        """Test that boundary values (0 and 1) are accepted."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        # Zero probability
        result = create_prediction(
            model_id=1,
            market_id=42,
            predicted_probability=Decimal("0.0000"),
        )
        assert result == 1

        # One probability
        result = create_prediction(
            model_id=1,
            market_id=42,
            predicted_probability=Decimal("1.0000"),
        )
        assert result == 1

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_prediction_allows_negative_edge(self, mock_get_cursor):
        """Test that negative edge values are accepted (prediction below market)."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = create_prediction(
            model_id=1,
            market_id=42,
            predicted_probability=Decimal("0.4000"),
            edge=Decimal("-0.1500"),
        )

        assert result == 1

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_prediction_allows_none_model_id(self, mock_get_cursor):
        """Test that model_id=None is accepted (e.g. ensemble prediction)."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = create_prediction(
            model_id=None,
            market_id=42,
            predicted_probability=Decimal("0.6500"),
        )

        assert result == 1


@pytest.mark.unit
class TestResolvePrediction:
    """Unit tests for resolve_prediction function."""

    @patch("precog.database.crud_analytics.get_cursor")
    def test_resolve_prediction_returns_true(self, mock_get_cursor):
        """Test resolve_prediction returns True on success."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = resolve_prediction(
            prediction_id=1,
            actual_outcome=Decimal("1.0000"),
            is_correct=True,
        )

        assert result is True

    @patch("precog.database.crud_analytics.get_cursor")
    def test_resolve_prediction_returns_false_when_not_found(self, mock_get_cursor):
        """Test resolve_prediction returns False when prediction_id not found."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = None

        result = resolve_prediction(
            prediction_id=999,
            actual_outcome=Decimal("1.0000"),
            is_correct=True,
        )

        assert result is False

    @patch("precog.database.crud_analytics.get_cursor")
    def test_resolve_prediction_validates_decimal_actual_outcome(self, mock_get_cursor):
        """Test that float values are rejected for actual_outcome."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(TypeError, match="actual_outcome must be Decimal"):
            resolve_prediction(prediction_id=1, actual_outcome=1.0, is_correct=True)

    @patch("precog.database.crud_analytics.get_cursor")
    def test_resolve_prediction_validates_actual_outcome_range_low(self, mock_get_cursor):
        """Test that actual_outcome below 0 is rejected."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(ValueError, match="actual_outcome must be between 0 and 1"):
            resolve_prediction(prediction_id=1, actual_outcome=Decimal("-0.0100"), is_correct=False)

    @patch("precog.database.crud_analytics.get_cursor")
    def test_resolve_prediction_validates_actual_outcome_range_high(self, mock_get_cursor):
        """Test that actual_outcome above 1 is rejected."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(ValueError, match="actual_outcome must be between 0 and 1"):
            resolve_prediction(prediction_id=1, actual_outcome=Decimal("1.0100"), is_correct=False)

    @patch("precog.database.crud_analytics.get_cursor")
    def test_resolve_prediction_allows_boundary_values(self, mock_get_cursor):
        """Test that boundary values 0 and 1 are accepted for actual_outcome."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = resolve_prediction(
            prediction_id=1, actual_outcome=Decimal("0.0000"), is_correct=False
        )
        assert result is True

        result = resolve_prediction(
            prediction_id=2, actual_outcome=Decimal("1.0000"), is_correct=True
        )
        assert result is True


@pytest.mark.unit
class TestGetPredictionsByRun:
    """Unit tests for get_predictions_by_run function."""

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_predictions_by_run_returns_list(self, mock_fetch_all):
        """Test that result is a list of dicts."""
        mock_fetch_all.return_value = [
            {"id": 1, "predicted_probability": Decimal("0.6500")},
            {"id": 2, "predicted_probability": Decimal("0.7200")},
        ]

        result = get_predictions_by_run(evaluation_run_id=1)

        assert len(result) == 2
        assert result[0]["id"] == 1

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_predictions_by_run_returns_empty_list(self, mock_fetch_all):
        """Test that empty result set returns empty list."""
        mock_fetch_all.return_value = []

        result = get_predictions_by_run(evaluation_run_id=999)

        assert result == []

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_predictions_by_run_orders_by_predicted_at_desc(self, mock_fetch_all):
        """Test that query orders by predicted_at DESC, id DESC."""
        mock_fetch_all.return_value = []

        get_predictions_by_run(evaluation_run_id=1)

        query = mock_fetch_all.call_args[0][0]
        assert "ORDER BY predicted_at DESC, id DESC" in query

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_predictions_by_run_default_limit(self, mock_fetch_all):
        """Test that default limit of 100 is applied."""
        mock_fetch_all.return_value = []

        get_predictions_by_run(evaluation_run_id=1)

        params = mock_fetch_all.call_args[0][1]
        assert 100 in params

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_predictions_by_run_custom_limit(self, mock_fetch_all):
        """Test that custom limit is applied."""
        mock_fetch_all.return_value = []

        get_predictions_by_run(evaluation_run_id=1, limit=25)

        params = mock_fetch_all.call_args[0][1]
        assert 25 in params


@pytest.mark.unit
class TestGetUnresolvedPredictions:
    """Unit tests for get_unresolved_predictions function."""

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_unresolved_predictions_returns_list(self, mock_fetch_all):
        """Test that result is a list of unresolved predictions."""
        mock_fetch_all.return_value = [
            {"id": 3, "actual_outcome": None},
        ]

        result = get_unresolved_predictions()

        assert len(result) == 1
        assert result[0]["actual_outcome"] is None

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_unresolved_predictions_filters_null_outcome(self, mock_fetch_all):
        """Test that query filters WHERE actual_outcome IS NULL."""
        mock_fetch_all.return_value = []

        get_unresolved_predictions()

        query = mock_fetch_all.call_args[0][0]
        assert "actual_outcome IS NULL" in query

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_unresolved_predictions_orders_by_predicted_at_desc(self, mock_fetch_all):
        """Test that query orders by predicted_at DESC, id DESC."""
        mock_fetch_all.return_value = []

        get_unresolved_predictions()

        query = mock_fetch_all.call_args[0][0]
        assert "ORDER BY predicted_at DESC, id DESC" in query

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_unresolved_predictions_default_limit(self, mock_fetch_all):
        """Test that default limit of 100 is applied."""
        mock_fetch_all.return_value = []

        get_unresolved_predictions()

        params = mock_fetch_all.call_args[0][1]
        assert 100 in params

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_unresolved_predictions_custom_limit(self, mock_fetch_all):
        """Test that custom limit is applied."""
        mock_fetch_all.return_value = []

        get_unresolved_predictions(limit=50)

        params = mock_fetch_all.call_args[0][1]
        assert 50 in params


# =============================================================================
# PERFORMANCE METRICS TESTS
# =============================================================================


@pytest.mark.unit
class TestUpsertPerformanceMetric:
    """Unit tests for upsert_performance_metric function."""

    @patch("precog.database.crud_analytics.get_cursor")
    def test_upsert_performance_metric_returns_surrogate_id(self, mock_get_cursor):
        """Test upsert_performance_metric returns the integer surrogate PK."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = upsert_performance_metric(
            entity_type="model",
            entity_id=1,
            metric_name="brier_score",
            metric_value=Decimal("0.1500"),
        )

        assert result == 1

    @patch("precog.database.crud_analytics.get_cursor")
    def test_upsert_performance_metric_validates_entity_type(self, mock_get_cursor):
        """Test that invalid entity_type values are rejected."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(ValueError, match="entity_type must be one of"):
            upsert_performance_metric(
                entity_type="invalid",
                entity_id=1,
                metric_name="brier_score",
                metric_value=Decimal("0.1500"),
            )

    @patch("precog.database.crud_analytics.get_cursor")
    def test_upsert_performance_metric_accepts_all_valid_entity_types(self, mock_get_cursor):
        """Test that every valid entity_type is accepted."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        for entity_type in _VALID_ENTITY_TYPES:
            result = upsert_performance_metric(
                entity_type=entity_type,
                entity_id=1,
                metric_name="accuracy",
                metric_value=Decimal("0.8200"),
            )
            assert result == 1

    @patch("precog.database.crud_analytics.get_cursor")
    def test_upsert_performance_metric_validates_decimal_metric_value(self, mock_get_cursor):
        """Test that float values are rejected for metric_value."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(TypeError, match="metric_value must be Decimal"):
            upsert_performance_metric(
                entity_type="model",
                entity_id=1,
                metric_name="brier_score",
                metric_value=0.15,
            )

    @patch("precog.database.crud_analytics.get_cursor")
    def test_upsert_performance_metric_with_all_optional_fields(self, mock_get_cursor):
        """Test upsert_performance_metric with every optional parameter."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 10}

        result = upsert_performance_metric(
            entity_type="model",
            entity_id=1,
            metric_name="brier_score",
            metric_value=Decimal("0.1500"),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
            sample_size=500,
            metadata={"sport": "nfl", "market_type": "spread"},
        )

        assert result == 10

    @patch("precog.database.crud_analytics.get_cursor")
    def test_upsert_performance_metric_uses_on_conflict(self, mock_get_cursor):
        """Test that upsert query includes ON CONFLICT ... DO UPDATE."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        upsert_performance_metric(
            entity_type="model",
            entity_id=1,
            metric_name="accuracy",
            metric_value=Decimal("0.8200"),
        )

        execute_call = mock_cursor.execute.call_args[0][0]
        assert "ON CONFLICT" in execute_call
        assert "DO UPDATE" in execute_call


@pytest.mark.unit
class TestGetPerformanceMetrics:
    """Unit tests for get_performance_metrics function."""

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_performance_metrics_returns_list(self, mock_fetch_all):
        """Test that result is a list of dicts."""
        mock_fetch_all.return_value = [
            {"id": 1, "metric_name": "accuracy", "metric_value": Decimal("0.8200")},
        ]

        result = get_performance_metrics("model", entity_id=1)

        assert len(result) == 1
        assert result[0]["metric_name"] == "accuracy"

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_performance_metrics_returns_empty_list(self, mock_fetch_all):
        """Test that empty result set returns empty list."""
        mock_fetch_all.return_value = []

        result = get_performance_metrics("model", entity_id=999)

        assert result == []

    def test_get_performance_metrics_validates_entity_type(self):
        """Test that invalid entity_type is rejected."""
        with pytest.raises(ValueError, match="entity_type must be one of"):
            get_performance_metrics("invalid", entity_id=1)

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_performance_metrics_filters_by_metric_name(self, mock_fetch_all):
        """Test filtering by metric_name."""
        mock_fetch_all.return_value = []

        get_performance_metrics("model", entity_id=1, metric_name="brier_score")

        query = mock_fetch_all.call_args[0][0]
        params = mock_fetch_all.call_args[0][1]
        assert "metric_name = %s" in query
        assert "brier_score" in params

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_performance_metrics_orders_by_calculated_at_desc(self, mock_fetch_all):
        """Test that query orders by calculated_at DESC, id DESC."""
        mock_fetch_all.return_value = []

        get_performance_metrics("model", entity_id=1)

        query = mock_fetch_all.call_args[0][0]
        assert "ORDER BY calculated_at DESC, id DESC" in query

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_performance_metrics_without_metric_name_filter(self, mock_fetch_all):
        """Test that query works without metric_name filter."""
        mock_fetch_all.return_value = []

        get_performance_metrics("strategy", entity_id=5)

        query = mock_fetch_all.call_args[0][0]
        assert "metric_name" not in query or "metric_name = %s" not in query
