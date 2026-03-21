"""
Unit Tests for Market Trades CRUD Operations (Migration 0028).

Tests the market trades functions: upsert_market_trade, upsert_market_trades_batch,
get_market_trades, and get_latest_trade_time. Validates Decimal enforcement,
enum validation, optional parameter handling, batch operations, ON CONFLICT
idempotency, since filtering, and ordering.

Related:
- Migration 0028: market_trades
- Issue #402: Add market_trades table for public trade tape
- migration_batch_plan_v1.md: Migration 0028 spec

Usage:
    pytest tests/unit/database/test_market_trades_crud.py -v
    pytest tests/unit/database/test_market_trades_crud.py -v -m unit
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_operations import (
    _VALID_TAKER_SIDES,
    get_latest_trade_time,
    get_market_trades,
    upsert_market_trade,
    upsert_market_trades_batch,
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


def _default_trade_kwargs():
    """Return minimal valid kwargs for upsert_market_trade."""
    return {
        "platform_id": "kalshi",
        "external_trade_id": "abc-123-def",
        "market_internal_id": 42,
        "count": 10,
        "trade_time": datetime(2026, 1, 15, 20, 30, 0, tzinfo=UTC),
    }


def _default_trade_dict():
    """Return minimal valid dict for upsert_market_trades_batch."""
    return {
        "platform_id": "kalshi",
        "external_trade_id": "abc-123-def",
        "market_internal_id": 42,
        "count": 10,
        "trade_time": datetime(2026, 1, 15, 20, 30, 0, tzinfo=UTC),
    }


# =============================================================================
# UPSERT MARKET TRADE TESTS
# =============================================================================


@pytest.mark.unit
class TestUpsertMarketTrade:
    """Unit tests for upsert_market_trade function."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_returns_surrogate_id(self, mock_get_cursor):
        """Test upsert_market_trade returns the integer surrogate PK on insert."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = upsert_market_trade(**_default_trade_kwargs())

        assert result == 1

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_returns_none_on_conflict(self, mock_get_cursor):
        """Test upsert returns None when trade already exists (ON CONFLICT DO NOTHING)."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = None

        result = upsert_market_trade(**_default_trade_kwargs())

        assert result is None

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_validates_decimal_yes_price(self, mock_get_cursor):
        """Test that float values are rejected for yes_price."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_trade_kwargs()
        kwargs["yes_price"] = 0.55  # float -- should raise

        with pytest.raises(TypeError, match="yes_price must be Decimal"):
            upsert_market_trade(**kwargs)

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_validates_decimal_no_price(self, mock_get_cursor):
        """Test that float values are rejected for no_price."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_trade_kwargs()
        kwargs["no_price"] = 0.45  # float -- should raise

        with pytest.raises(TypeError, match="no_price must be Decimal"):
            upsert_market_trade(**kwargs)

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_validates_taker_side(self, mock_get_cursor):
        """Test that invalid taker_side values are rejected."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_trade_kwargs()
        kwargs["taker_side"] = "buy"  # invalid -- should raise

        with pytest.raises(ValueError, match="taker_side must be one of"):
            upsert_market_trade(**kwargs)

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_allows_none_optional_fields(self, mock_get_cursor):
        """Test that all optional fields accept None (default behavior)."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 2}

        # Only required fields -- yes_price, no_price, taker_side default to None
        result = upsert_market_trade(**_default_trade_kwargs())

        assert result == 2

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_with_all_optional_fields(self, mock_get_cursor):
        """Test upsert_market_trade with every optional parameter provided."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 99}

        result = upsert_market_trade(
            platform_id="kalshi",
            external_trade_id="abc-123-def",
            market_internal_id=42,
            count=10,
            trade_time=datetime(2026, 1, 15, 20, 30, 0, tzinfo=UTC),
            yes_price=Decimal("0.5500"),
            no_price=Decimal("0.4500"),
            taker_side="yes",
        )

        assert result == 99

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_accepts_all_valid_taker_sides(self, mock_get_cursor):
        """Test that every valid taker_side is accepted."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        for side in _VALID_TAKER_SIDES:
            kwargs = _default_trade_kwargs()
            kwargs["taker_side"] = side
            result = upsert_market_trade(**kwargs)
            assert result == 1

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_sql_contains_on_conflict(self, mock_get_cursor):
        """Test that the SQL uses ON CONFLICT DO NOTHING for idempotency."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        upsert_market_trade(**_default_trade_kwargs())

        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "ON CONFLICT" in sql
        assert "DO NOTHING" in sql

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_sql_contains_returning_id(self, mock_get_cursor):
        """Test that the SQL uses RETURNING id to get the surrogate PK."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        upsert_market_trade(**_default_trade_kwargs())

        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "RETURNING id" in sql


# =============================================================================
# UPSERT MARKET TRADES BATCH TESTS
# =============================================================================


@pytest.mark.unit
class TestUpsertMarketTradesBatch:
    """Unit tests for upsert_market_trades_batch function."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_batch_returns_rowcount(self, mock_get_cursor):
        """Test batch insert returns cur.rowcount (actual inserts, not skipped)."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 2

        rows = [_default_trade_dict(), _default_trade_dict()]
        rows[1]["external_trade_id"] = "xyz-456-ghi"

        result = upsert_market_trades_batch(rows)

        assert result == 2

    def test_batch_empty_list_returns_zero(self):
        """Test that empty list returns 0 without DB interaction."""
        result = upsert_market_trades_batch([])

        assert result == 0

    @patch("precog.database.crud_operations.get_cursor")
    def test_batch_validates_decimal_yes_price(self, mock_get_cursor):
        """Test that float yes_price is rejected in batch."""
        _mock_cursor_context(mock_get_cursor)

        row = _default_trade_dict()
        row["yes_price"] = 0.55  # float -- should raise

        with pytest.raises(TypeError, match="yes_price must be Decimal"):
            upsert_market_trades_batch([row])

    @patch("precog.database.crud_operations.get_cursor")
    def test_batch_validates_decimal_no_price(self, mock_get_cursor):
        """Test that float no_price is rejected in batch."""
        _mock_cursor_context(mock_get_cursor)

        row = _default_trade_dict()
        row["no_price"] = 0.45  # float -- should raise

        with pytest.raises(TypeError, match="no_price must be Decimal"):
            upsert_market_trades_batch([row])

    @patch("precog.database.crud_operations.get_cursor")
    def test_batch_validates_taker_side(self, mock_get_cursor):
        """Test that invalid taker_side is rejected in batch."""
        _mock_cursor_context(mock_get_cursor)

        row = _default_trade_dict()
        row["taker_side"] = "sell"

        with pytest.raises(ValueError, match="taker_side must be one of"):
            upsert_market_trades_batch([row])

    @patch("precog.database.crud_operations.get_cursor")
    def test_batch_calls_executemany(self, mock_get_cursor):
        """Test that batch insert uses executemany for efficiency."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        rows = [_default_trade_dict()]
        upsert_market_trades_batch(rows)

        mock_cursor.executemany.assert_called_once()

    @patch("precog.database.crud_operations.get_cursor")
    def test_batch_sql_contains_on_conflict(self, mock_get_cursor):
        """Test that batch SQL uses ON CONFLICT DO NOTHING."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        upsert_market_trades_batch([_default_trade_dict()])

        call_args = mock_cursor.executemany.call_args
        sql = call_args[0][0]
        assert "ON CONFLICT" in sql
        assert "DO NOTHING" in sql

    @patch("precog.database.crud_operations.get_cursor")
    def test_batch_allows_none_optional_fields(self, mock_get_cursor):
        """Test that batch rows without optional fields work fine."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        # Only required fields
        row = _default_trade_dict()
        upsert_market_trades_batch([row])

        call_args = mock_cursor.executemany.call_args
        params_list = call_args[0][1]
        # yes_price (index 4), no_price (index 5), taker_side (index 6) should be None
        assert params_list[0][4] is None
        assert params_list[0][5] is None
        assert params_list[0][6] is None


# =============================================================================
# GET MARKET TRADES TESTS
# =============================================================================


@pytest.mark.unit
class TestGetMarketTrades:
    """Unit tests for get_market_trades function."""

    @patch("precog.database.crud_operations.fetch_all")
    def test_returns_empty_list(self, mock_fetch_all):
        """Test that empty result set returns empty list."""
        mock_fetch_all.return_value = []

        result = get_market_trades(42)

        assert result == []

    @patch("precog.database.crud_operations.fetch_all")
    def test_returns_list_of_dicts(self, mock_fetch_all):
        """Test that result is a list of dicts."""
        mock_fetch_all.return_value = [
            {"id": 1, "market_internal_id": 42, "count": 10},
            {"id": 2, "market_internal_id": 42, "count": 5},
        ]

        result = get_market_trades(42)

        assert len(result) == 2
        assert result[0]["id"] == 1

    @patch("precog.database.crud_operations.fetch_all")
    def test_filters_by_since(self, mock_fetch_all):
        """Test that since parameter adds trade_time filter."""
        mock_fetch_all.return_value = []
        cutoff = datetime(2026, 1, 15, 20, 0, 0, tzinfo=UTC)

        get_market_trades(42, since=cutoff)

        query = mock_fetch_all.call_args[0][0]
        params = mock_fetch_all.call_args[0][1]
        assert "trade_time >= %s" in query
        assert cutoff in params

    @patch("precog.database.crud_operations.fetch_all")
    def test_respects_limit(self, mock_fetch_all):
        """Test that custom limit is applied."""
        mock_fetch_all.return_value = []

        get_market_trades(42, limit=25)

        params = mock_fetch_all.call_args[0][1]
        assert 25 in params

    @patch("precog.database.crud_operations.fetch_all")
    def test_default_limit(self, mock_fetch_all):
        """Test that default limit of 100 is applied."""
        mock_fetch_all.return_value = []

        get_market_trades(42)

        params = mock_fetch_all.call_args[0][1]
        assert 100 in params

    @patch("precog.database.crud_operations.fetch_all")
    def test_orders_by_trade_time_desc(self, mock_fetch_all):
        """Test that query orders by trade_time DESC, id DESC."""
        mock_fetch_all.return_value = []

        get_market_trades(42)

        query = mock_fetch_all.call_args[0][0]
        assert "ORDER BY trade_time DESC, id DESC" in query

    @patch("precog.database.crud_operations.fetch_all")
    def test_filters_by_market_internal_id(self, mock_fetch_all):
        """Test that query filters by market_internal_id."""
        mock_fetch_all.return_value = []

        get_market_trades(42)

        query = mock_fetch_all.call_args[0][0]
        params = mock_fetch_all.call_args[0][1]
        assert "market_internal_id = %s" in query
        assert 42 in params

    @patch("precog.database.crud_operations.fetch_all")
    def test_no_since_omits_time_filter(self, mock_fetch_all):
        """Test that omitting since does not add time filter."""
        mock_fetch_all.return_value = []

        get_market_trades(42)

        query = mock_fetch_all.call_args[0][0]
        assert "trade_time >= %s" not in query


# =============================================================================
# GET LATEST TRADE TIME TESTS
# =============================================================================


@pytest.mark.unit
class TestGetLatestTradeTime:
    """Unit tests for get_latest_trade_time function."""

    @patch("precog.database.crud_operations.fetch_one")
    def test_returns_datetime_from_latest(self, mock_fetch_one):
        """Test that function returns trade_time from the most recent trade."""
        expected = datetime(2026, 1, 15, 20, 30, 0, tzinfo=UTC)
        mock_fetch_one.return_value = {"trade_time": expected}

        result = get_latest_trade_time(42)

        assert result == expected

    @patch("precog.database.crud_operations.fetch_one")
    def test_returns_none_when_empty(self, mock_fetch_one):
        """Test that function returns None when no trades exist for this market."""
        mock_fetch_one.return_value = None

        result = get_latest_trade_time(42)

        assert result is None

    @patch("precog.database.crud_operations.fetch_one")
    def test_queries_correct_market(self, mock_fetch_one):
        """Test that query filters by the given market_internal_id."""
        mock_fetch_one.return_value = None

        get_latest_trade_time(99)

        params = mock_fetch_one.call_args[0][1]
        assert 99 in params

    @patch("precog.database.crud_operations.fetch_one")
    def test_orders_by_trade_time_desc(self, mock_fetch_one):
        """Test that query orders by trade_time DESC, id DESC with LIMIT 1."""
        mock_fetch_one.return_value = None

        get_latest_trade_time(42)

        query = mock_fetch_one.call_args[0][0]
        assert "ORDER BY trade_time DESC, id DESC" in query
        assert "LIMIT 1" in query
