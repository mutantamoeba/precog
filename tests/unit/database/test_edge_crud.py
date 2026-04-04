"""
Unit Tests for Edge CRUD Operations (Migration 0023).

Tests the edge lifecycle CRUD functions: create, update outcome/status,
query by strategy, and edge_lifecycle view queries.

Related:
- Migration 0023: edges enrichment and cleanup
- ADR-002: Decimal Precision for All Financial Data
- Pattern 2: Dual Versioning System (SCD Type 2)

Usage:
    pytest tests/unit/database/test_edge_crud.py -v
    pytest tests/unit/database/test_edge_crud.py -v -m unit
"""

import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_analytics import (
    create_edge,
    get_edge_lifecycle,
    get_edges_by_strategy,
    update_edge_outcome,
    update_edge_status,
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
# CREATE EDGE TESTS
# =============================================================================


@pytest.mark.unit
class TestCreateEdge:
    """Unit tests for create_edge function."""

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_edge_returns_surrogate_id(self, mock_get_cursor):
        """Test create_edge returns the integer surrogate PK."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 42}

        result = create_edge(
            market_internal_id=1,
            model_id=2,
            expected_value=Decimal("0.0500"),
            true_win_probability=Decimal("0.5700"),
            market_implied_probability=Decimal("0.5200"),
            market_price=Decimal("0.5200"),
        )

        assert result == 42

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_edge_auto_generates_edge_id(self, mock_get_cursor):
        """Test that edge_id is set to EDGE-{id} after insert."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 7}

        create_edge(
            market_internal_id=1,
            model_id=2,
            expected_value=Decimal("0.0500"),
            true_win_probability=Decimal("0.5700"),
            market_implied_probability=Decimal("0.5200"),
            market_price=Decimal("0.5200"),
        )

        # Second execute call should be the UPDATE for edge_id
        calls = mock_cursor.execute.call_args_list
        assert len(calls) == 2
        update_call = calls[1]
        assert "EDGE-7" in str(update_call)

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_edge_validates_decimal_fields(self, mock_get_cursor):
        """Test that float values are rejected for Decimal fields."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(TypeError, match="expected_value must be Decimal"):
            create_edge(
                market_internal_id=1,
                model_id=2,
                expected_value=0.05,  # float -- should raise
                true_win_probability=Decimal("0.5700"),
                market_implied_probability=Decimal("0.5200"),
                market_price=Decimal("0.5200"),
            )

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_edge_validates_optional_decimal_fields(self, mock_get_cursor):
        """Test that optional Decimal fields also reject floats."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(TypeError, match="yes_ask_price must be Decimal"):
            create_edge(
                market_internal_id=1,
                model_id=2,
                expected_value=Decimal("0.0500"),
                true_win_probability=Decimal("0.5700"),
                market_implied_probability=Decimal("0.5200"),
                market_price=Decimal("0.5200"),
                yes_ask_price=0.53,  # float -- should raise
            )

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_edge_with_all_optional_fields(self, mock_get_cursor):
        """Test create_edge with every optional parameter provided."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 99}

        result = create_edge(
            market_internal_id=1,
            model_id=2,
            expected_value=Decimal("0.0500"),
            true_win_probability=Decimal("0.5700"),
            market_implied_probability=Decimal("0.5200"),
            market_price=Decimal("0.5200"),
            yes_ask_price=Decimal("0.5300"),
            no_ask_price=Decimal("0.4800"),
            spread=Decimal("0.0100"),
            volume=1500,
            open_interest=3200,
            last_price=Decimal("0.5250"),
            liquidity=Decimal("50000.0000"),
            strategy_id=1,
            confidence_level="high",
            confidence_metrics={"model_agreement": 0.95},
            recommended_action="auto_execute",
            category="sports",
            subcategory="nfl",
            execution_environment="paper",
        )

        assert result == 99
        # Verify INSERT was called with confidence_metrics as JSON
        insert_call = mock_cursor.execute.call_args_list[0]
        insert_params = insert_call[0][1]
        # confidence_metrics should be JSON-serialized (16th param, 0-indexed 15)
        assert json.loads(insert_params[15]) == {"model_agreement": 0.95}

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_edge_sets_edge_status_detected(self, mock_get_cursor):
        """Test that new edges default to edge_status='detected'."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        create_edge(
            market_internal_id=1,
            model_id=2,
            expected_value=Decimal("0.0500"),
            true_win_probability=Decimal("0.5700"),
            market_implied_probability=Decimal("0.5200"),
            market_price=Decimal("0.5200"),
        )

        insert_sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "'detected'" in insert_sql

    @patch("precog.database.crud_analytics.get_cursor")
    def test_create_edge_sets_row_current_ind_true(self, mock_get_cursor):
        """Test that new edges have row_current_ind = TRUE."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        create_edge(
            market_internal_id=1,
            model_id=2,
            expected_value=Decimal("0.0500"),
            true_win_probability=Decimal("0.5700"),
            market_implied_probability=Decimal("0.5200"),
            market_price=Decimal("0.5200"),
        )

        insert_sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "TRUE" in insert_sql
        assert "row_current_ind" in insert_sql


# =============================================================================
# UPDATE EDGE OUTCOME TESTS
# =============================================================================


@pytest.mark.unit
class TestUpdateEdgeOutcome:
    """Unit tests for update_edge_outcome function."""

    @patch("precog.database.crud_analytics.get_cursor")
    def test_update_edge_outcome_success(self, mock_get_cursor):
        """Test successful outcome update returns True."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        result = update_edge_outcome(
            edge_pk=42,
            actual_outcome="yes",
            settlement_value=Decimal("1.0000"),
        )

        assert result is True

    @patch("precog.database.crud_analytics.get_cursor")
    def test_update_edge_outcome_not_found(self, mock_get_cursor):
        """Test outcome update returns False when edge not found."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 0

        result = update_edge_outcome(
            edge_pk=999,
            actual_outcome="no",
            settlement_value=Decimal("0.0000"),
        )

        assert result is False

    @patch("precog.database.crud_analytics.get_cursor")
    def test_update_edge_outcome_sets_status_settled(self, mock_get_cursor):
        """Test that outcome update sets edge_status to 'settled'."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        update_edge_outcome(
            edge_pk=42,
            actual_outcome="yes",
            settlement_value=Decimal("1.0000"),
        )

        sql = mock_cursor.execute.call_args[0][0]
        assert "settled" in sql
        assert "row_current_ind = TRUE" in sql

    @patch("precog.database.crud_analytics.get_cursor")
    def test_update_edge_outcome_validates_decimal(self, mock_get_cursor):
        """Test that settlement_value rejects floats."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(TypeError, match="settlement_value must be Decimal"):
            update_edge_outcome(
                edge_pk=42,
                actual_outcome="yes",
                settlement_value=1.0,  # float -- should raise
            )

    @patch("precog.database.crud_analytics.get_cursor")
    def test_update_edge_outcome_invalid_outcome(self, mock_get_cursor):
        """Test that invalid outcome values are rejected."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(ValueError, match="actual_outcome must be one of"):
            update_edge_outcome(
                edge_pk=42,
                actual_outcome="maybe",  # invalid
                settlement_value=Decimal("1.0000"),
            )

    @patch("precog.database.crud_analytics.get_cursor")
    def test_update_edge_outcome_with_resolved_at(self, mock_get_cursor):
        """Test outcome update with explicit resolved_at timestamp."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        resolved = datetime(2026, 3, 21, 12, 0, 0, tzinfo=UTC)
        update_edge_outcome(
            edge_pk=42,
            actual_outcome="void",
            settlement_value=Decimal("0.0000"),
            resolved_at=resolved,
        )

        params = mock_cursor.execute.call_args[0][1]
        assert params[2] == resolved


# =============================================================================
# UPDATE EDGE STATUS TESTS
# =============================================================================


@pytest.mark.unit
class TestUpdateEdgeStatus:
    """Unit tests for update_edge_status function."""

    @patch("precog.database.crud_analytics.get_cursor")
    def test_update_edge_status_success(self, mock_get_cursor):
        """Test successful status transition returns True."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        result = update_edge_status(edge_pk=42, new_status="recommended")

        assert result is True

    @patch("precog.database.crud_analytics.get_cursor")
    def test_update_edge_status_not_found(self, mock_get_cursor):
        """Test status update returns False when edge not found."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 0

        result = update_edge_status(edge_pk=999, new_status="recommended")

        assert result is False

    @patch("precog.database.crud_analytics.get_cursor")
    def test_update_edge_status_invalid_status(self, mock_get_cursor):
        """Test that invalid status values are rejected."""
        _mock_cursor_context(mock_get_cursor)

        with pytest.raises(ValueError, match="new_status must be one of"):
            update_edge_status(edge_pk=42, new_status="invalid_status")

    @patch("precog.database.crud_analytics.get_cursor")
    def test_update_edge_status_all_valid_statuses(self, mock_get_cursor):
        """Test that all valid statuses are accepted."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        valid_statuses = [
            "detected",
            "recommended",
            "acted_on",
            "expired",
            "settled",
            "void",
        ]
        for status in valid_statuses:
            result = update_edge_status(edge_pk=42, new_status=status)
            assert result is True

    @patch("precog.database.crud_analytics.get_cursor")
    def test_update_edge_status_filters_by_row_current_ind(self, mock_get_cursor):
        """Test that status update only targets current SCD rows."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        update_edge_status(edge_pk=42, new_status="acted_on")

        sql = mock_cursor.execute.call_args[0][0]
        assert "row_current_ind = TRUE" in sql


# =============================================================================
# GET EDGES BY STRATEGY TESTS
# =============================================================================


@pytest.mark.unit
class TestGetEdgesByStrategy:
    """Unit tests for get_edges_by_strategy function."""

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_edges_by_strategy_basic(self, mock_fetch_all):
        """Test basic query with only strategy_id."""
        mock_fetch_all.return_value = [
            {"id": 1, "edge_id": "EDGE-1", "strategy_id": 5},
            {"id": 2, "edge_id": "EDGE-2", "strategy_id": 5},
        ]

        result = get_edges_by_strategy(strategy_id=5)

        assert len(result) == 2
        mock_fetch_all.assert_called_once()
        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        assert "row_current_ind = TRUE" in sql
        assert "strategy_id = %s" in sql

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_edges_by_strategy_with_status_filter(self, mock_fetch_all):
        """Test query with edge_status filter."""
        mock_fetch_all.return_value = []

        get_edges_by_strategy(strategy_id=5, edge_status="detected")

        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "edge_status = %s" in sql
        assert "detected" in params

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_edges_by_strategy_with_exec_env_filter(self, mock_fetch_all):
        """Test query with execution_environment filter."""
        mock_fetch_all.return_value = []

        get_edges_by_strategy(strategy_id=5, execution_environment="paper")

        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "execution_environment = %s" in sql
        assert "paper" in params

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_edges_by_strategy_with_all_filters(self, mock_fetch_all):
        """Test query with all optional filters."""
        mock_fetch_all.return_value = []

        get_edges_by_strategy(
            strategy_id=5,
            edge_status="settled",
            execution_environment="live",
            limit=50,
        )

        call_args = mock_fetch_all.call_args
        params = call_args[0][1]
        # Params: strategy_id, edge_status, execution_environment, limit
        assert params == (5, "settled", "live", 50)

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_edges_by_strategy_default_limit(self, mock_fetch_all):
        """Test that default limit is 100."""
        mock_fetch_all.return_value = []

        get_edges_by_strategy(strategy_id=5)

        call_args = mock_fetch_all.call_args
        params = call_args[0][1]
        # Last param should be limit = 100
        assert params[-1] == 100

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_edges_by_strategy_orders_by_created_at_desc(self, mock_fetch_all):
        """Test that results are ordered by created_at DESC."""
        mock_fetch_all.return_value = []

        get_edges_by_strategy(strategy_id=5)

        sql = mock_fetch_all.call_args[0][0]
        assert "ORDER BY created_at DESC" in sql


# =============================================================================
# GET EDGE LIFECYCLE TESTS
# =============================================================================


@pytest.mark.unit
class TestGetEdgeLifecycle:
    """Unit tests for get_edge_lifecycle function."""

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_edge_lifecycle_returns_computed_fields(self, mock_fetch_all):
        """Test that query selects realized_pnl and hours_to_resolution."""
        mock_fetch_all.return_value = [
            {
                "id": 1,
                "edge_id": "EDGE-1",
                "realized_pnl": Decimal("0.4800"),
                "hours_to_resolution": 24.5,
            }
        ]

        result = get_edge_lifecycle()

        assert len(result) == 1
        assert result[0]["realized_pnl"] == Decimal("0.4800")
        assert result[0]["hours_to_resolution"] == 24.5

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_edge_lifecycle_queries_view(self, mock_fetch_all):
        """Test that query uses the edge_lifecycle view."""
        mock_fetch_all.return_value = []

        get_edge_lifecycle()

        sql = mock_fetch_all.call_args[0][0]
        assert "edge_lifecycle" in sql
        assert "realized_pnl" in sql
        assert "hours_to_resolution" in sql

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_edge_lifecycle_filter_by_market(self, mock_fetch_all):
        """Test filtering by market_internal_id."""
        mock_fetch_all.return_value = []

        get_edge_lifecycle(market_internal_id=42)

        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "market_internal_id = %s" in sql
        assert 42 in params

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_edge_lifecycle_filter_by_strategy(self, mock_fetch_all):
        """Test filtering by strategy_id."""
        mock_fetch_all.return_value = []

        get_edge_lifecycle(strategy_id=5)

        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "strategy_id = %s" in sql
        assert 5 in params

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_edge_lifecycle_with_both_filters(self, mock_fetch_all):
        """Test filtering by both market and strategy."""
        mock_fetch_all.return_value = []

        get_edge_lifecycle(market_internal_id=42, strategy_id=5, limit=25)

        call_args = mock_fetch_all.call_args
        params = call_args[0][1]
        assert params == (42, 5, 25)

    @patch("precog.database.crud_analytics.fetch_all")
    def test_get_edge_lifecycle_default_limit(self, mock_fetch_all):
        """Test that default limit is 100."""
        mock_fetch_all.return_value = []

        get_edge_lifecycle()

        call_args = mock_fetch_all.call_args
        params = call_args[0][1]
        assert params[-1] == 100
