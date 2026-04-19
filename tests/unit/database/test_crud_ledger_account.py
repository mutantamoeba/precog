"""
Unit Tests for Account Ledger CRUD Operations (Migration 0026).

Tests the append-only ledger functions: create_ledger_entry, get_ledger_entries,
and get_running_balance. Validates Decimal enforcement, enum validation, optional
parameter handling, filtering, and ordering.

Related:
- Migration 0026: account_ledger
- ADR-002: Decimal Precision for All Financial Data
- migration_batch_plan_v1.md: Migration 0026 spec

Usage:
    pytest tests/unit/database/test_crud_ledger_account.py -v
    pytest tests/unit/database/test_crud_ledger_account.py -v -m unit
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_ledger import (
    _VALID_REFERENCE_TYPES,
    _VALID_TRANSACTION_TYPES,
    create_ledger_entry,
    get_ledger_entries,
    get_running_balance,
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


def _default_ledger_kwargs():
    """Return minimal valid kwargs for create_ledger_entry."""
    return {
        "platform_id": "kalshi",
        "transaction_type": "deposit",
        "amount": Decimal("500.0000"),
        "running_balance": Decimal("1500.0000"),
    }


# =============================================================================
# CREATE LEDGER ENTRY TESTS
# =============================================================================


@pytest.mark.unit
class TestCreateLedgerEntry:
    """Unit tests for create_ledger_entry function."""

    @patch("precog.database.crud_ledger.get_cursor")
    def test_create_ledger_entry_returns_surrogate_id(self, mock_get_cursor):
        """Test create_ledger_entry returns the integer surrogate PK."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = create_ledger_entry(**_default_ledger_kwargs())

        assert result == 1

    @patch("precog.database.crud_ledger.get_cursor")
    def test_create_ledger_entry_validates_decimal_amount(self, mock_get_cursor):
        """Test that float values are rejected for amount."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_ledger_kwargs()
        kwargs["amount"] = 500.0  # float -- should raise

        with pytest.raises(TypeError, match="amount must be Decimal"):
            create_ledger_entry(**kwargs)

    @patch("precog.database.crud_ledger.get_cursor")
    def test_create_ledger_entry_validates_decimal_running_balance(self, mock_get_cursor):
        """Test that float values are rejected for running_balance."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_ledger_kwargs()
        kwargs["running_balance"] = 1500.0  # float -- should raise

        with pytest.raises(TypeError, match="running_balance must be Decimal"):
            create_ledger_entry(**kwargs)

    @patch("precog.database.crud_ledger.get_cursor")
    def test_create_ledger_entry_validates_transaction_type(self, mock_get_cursor):
        """Test that invalid transaction_type values are rejected."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_ledger_kwargs()
        kwargs["transaction_type"] = "refund"

        with pytest.raises(ValueError, match="transaction_type must be one of"):
            create_ledger_entry(**kwargs)

    @patch("precog.database.crud_ledger.get_cursor")
    def test_create_ledger_entry_validates_reference_type(self, mock_get_cursor):
        """Test that invalid reference_type values are rejected."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_ledger_kwargs()
        kwargs["reference_type"] = "external"

        with pytest.raises(ValueError, match="reference_type must be one of"):
            create_ledger_entry(**kwargs)

    @patch("precog.database.crud_ledger.get_cursor")
    def test_create_ledger_entry_allows_none_reference_type(self, mock_get_cursor):
        """Test that reference_type=None is accepted (not validated)."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 2}

        kwargs = _default_ledger_kwargs()
        kwargs["reference_type"] = None

        result = create_ledger_entry(**kwargs)

        assert result == 2

    @patch("precog.database.crud_ledger.get_cursor")
    def test_create_ledger_entry_validates_running_balance_non_negative(self, mock_get_cursor):
        """Test that negative running_balance is rejected."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_ledger_kwargs()
        kwargs["running_balance"] = Decimal("-1.0000")

        with pytest.raises(ValueError, match="running_balance must be >= 0"):
            create_ledger_entry(**kwargs)

    @patch("precog.database.crud_ledger.get_cursor")
    def test_create_ledger_entry_allows_zero_running_balance(self, mock_get_cursor):
        """Test that running_balance=0 is accepted (boundary value)."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 10}

        kwargs = _default_ledger_kwargs()
        kwargs["running_balance"] = Decimal("0.0000")
        kwargs["transaction_type"] = "withdrawal"
        kwargs["amount"] = Decimal("-1500.0000")

        result = create_ledger_entry(**kwargs)

        assert result == 10

    @patch("precog.database.crud_ledger.get_cursor")
    def test_create_ledger_entry_allows_negative_amount(self, mock_get_cursor):
        """Test that negative amounts are allowed (withdrawals, fees)."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 3}

        kwargs = _default_ledger_kwargs()
        kwargs["amount"] = Decimal("-25.0000")
        kwargs["transaction_type"] = "fee"

        result = create_ledger_entry(**kwargs)

        assert result == 3

    @patch("precog.database.crud_ledger.get_cursor")
    def test_create_ledger_entry_with_all_optional_fields(self, mock_get_cursor):
        """Test create_ledger_entry with every optional parameter provided."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 99}

        result = create_ledger_entry(
            platform_id="kalshi",
            transaction_type="trade_pnl",
            amount=Decimal("50.0000"),
            running_balance=Decimal("1550.0000"),
            currency="USD",
            reference_type="order",
            reference_id=42,
            order_id=42,
            description="Profit from YES contract fill",
        )

        assert result == 99

    @patch("precog.database.crud_ledger.get_cursor")
    def test_create_ledger_entry_accepts_all_valid_transaction_types(self, mock_get_cursor):
        """Test that every valid transaction_type is accepted."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        for txn_type in _VALID_TRANSACTION_TYPES:
            kwargs = _default_ledger_kwargs()
            kwargs["transaction_type"] = txn_type
            result = create_ledger_entry(**kwargs)
            assert result == 1

    @patch("precog.database.crud_ledger.get_cursor")
    def test_create_ledger_entry_accepts_all_valid_reference_types(self, mock_get_cursor):
        """Test that every valid reference_type is accepted."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        for ref_type in _VALID_REFERENCE_TYPES:
            kwargs = _default_ledger_kwargs()
            kwargs["reference_type"] = ref_type
            kwargs["reference_id"] = 1
            result = create_ledger_entry(**kwargs)
            assert result == 1


# =============================================================================
# GET LEDGER ENTRIES TESTS
# =============================================================================


@pytest.mark.unit
class TestGetLedgerEntries:
    """Unit tests for get_ledger_entries function."""

    @patch("precog.database.crud_ledger.fetch_all")
    def test_get_ledger_entries_returns_empty_list(self, mock_fetch_all):
        """Test that empty result set returns empty list."""
        mock_fetch_all.return_value = []

        result = get_ledger_entries("kalshi")

        assert result == []

    def test_get_ledger_entries_validates_transaction_type(self):
        """Test that invalid transaction_type is rejected."""
        with pytest.raises(ValueError, match="transaction_type must be one of"):
            get_ledger_entries("kalshi", transaction_type="refund")

    @patch("precog.database.crud_ledger.fetch_all")
    def test_get_ledger_entries_returns_list(self, mock_fetch_all):
        """Test that result is a list of dicts."""
        mock_fetch_all.return_value = [
            {"id": 1, "transaction_type": "deposit", "amount": Decimal("500.0000")},
            {"id": 2, "transaction_type": "fee", "amount": Decimal("-0.0200")},
        ]

        result = get_ledger_entries("kalshi")

        assert len(result) == 2
        assert result[0]["id"] == 1

    @patch("precog.database.crud_ledger.fetch_all")
    def test_get_ledger_entries_filters_by_type(self, mock_fetch_all):
        """Test filtering by transaction_type."""
        mock_fetch_all.return_value = []

        get_ledger_entries("kalshi", transaction_type="fee")

        query = mock_fetch_all.call_args[0][0]
        params = mock_fetch_all.call_args[0][1]
        assert "transaction_type = %s" in query
        assert "fee" in params

    @patch("precog.database.crud_ledger.fetch_all")
    def test_get_ledger_entries_filters_by_since(self, mock_fetch_all):
        """Test filtering by since datetime."""
        mock_fetch_all.return_value = []
        cutoff = datetime(2026, 3, 21, 12, 0, 0, tzinfo=UTC)

        get_ledger_entries("kalshi", since=cutoff)

        query = mock_fetch_all.call_args[0][0]
        params = mock_fetch_all.call_args[0][1]
        assert "created_at >= %s" in query
        assert cutoff in params

    @patch("precog.database.crud_ledger.fetch_all")
    def test_get_ledger_entries_respects_limit(self, mock_fetch_all):
        """Test that custom limit is applied."""
        mock_fetch_all.return_value = []

        get_ledger_entries("kalshi", limit=25)

        params = mock_fetch_all.call_args[0][1]
        assert 25 in params

    @patch("precog.database.crud_ledger.fetch_all")
    def test_get_ledger_entries_default_limit(self, mock_fetch_all):
        """Test that default limit of 100 is applied."""
        mock_fetch_all.return_value = []

        get_ledger_entries("kalshi")

        params = mock_fetch_all.call_args[0][1]
        assert 100 in params

    @patch("precog.database.crud_ledger.fetch_all")
    def test_get_ledger_entries_orders_by_created_at_desc(self, mock_fetch_all):
        """Test that query orders by created_at DESC."""
        mock_fetch_all.return_value = []

        get_ledger_entries("kalshi")

        query = mock_fetch_all.call_args[0][0]
        assert "ORDER BY created_at DESC, id DESC" in query

    @patch("precog.database.crud_ledger.fetch_all")
    def test_get_ledger_entries_combines_filters(self, mock_fetch_all):
        """Test combining transaction_type and since filters."""
        mock_fetch_all.return_value = []
        cutoff = datetime(2026, 3, 21, 12, 0, 0, tzinfo=UTC)

        get_ledger_entries("kalshi", transaction_type="deposit", since=cutoff)

        query = mock_fetch_all.call_args[0][0]
        assert "transaction_type = %s" in query
        assert "created_at >= %s" in query


# =============================================================================
# GET RUNNING BALANCE TESTS
# =============================================================================


@pytest.mark.unit
class TestGetRunningBalance:
    """Unit tests for get_running_balance function."""

    @patch("precog.database.crud_ledger.fetch_one")
    def test_get_running_balance_returns_decimal(self, mock_fetch_one):
        """Test that running_balance is returned as Decimal from latest entry."""
        mock_fetch_one.return_value = {"running_balance": Decimal("1500.0000")}

        result = get_running_balance("kalshi")

        assert result == Decimal("1500.0000")
        assert isinstance(result, Decimal)

    @patch("precog.database.crud_ledger.fetch_one")
    def test_get_running_balance_returns_none_when_empty(self, mock_fetch_one):
        """Test that None is returned when no ledger entries exist."""
        mock_fetch_one.return_value = None

        result = get_running_balance("kalshi")

        assert result is None

    @patch("precog.database.crud_ledger.fetch_one")
    def test_get_running_balance_queries_latest_entry(self, mock_fetch_one):
        """Test that query orders by created_at DESC LIMIT 1."""
        mock_fetch_one.return_value = {"running_balance": Decimal("1000.0000")}

        get_running_balance("kalshi")

        query = mock_fetch_one.call_args[0][0]
        assert "ORDER BY created_at DESC, id DESC" in query
        assert "LIMIT 1" in query

    @patch("precog.database.crud_ledger.fetch_one")
    def test_get_running_balance_filters_by_platform(self, mock_fetch_one):
        """Test that query filters by platform_id."""
        mock_fetch_one.return_value = {"running_balance": Decimal("1000.0000")}

        get_running_balance("kalshi")

        query = mock_fetch_one.call_args[0][0]
        params = mock_fetch_one.call_args[0][1]
        assert "platform_id = %s" in query
        assert "kalshi" in params
