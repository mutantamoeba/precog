"""
Unit Tests for Circuit Breaker CRUD Operations.

Tests the circuit_breaker_events table CRUD functions:
create_circuit_breaker_event, resolve_circuit_breaker, get_active_breakers.

The circuit_breaker_events table is a safety guard for trading operations.
These tests verify the CRUD layer in isolation with mocked database connections.

Related:
    - Migration 0001: circuit_breaker_events table schema
    - Issue #390: Wire circuit_breaker_events table
    - REQ-OBSERV-001: Observability Requirements

Usage:
    pytest tests/unit/database/test_crud_circuit_breaker.py -v
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_system import (
    create_circuit_breaker_event,
    get_active_breakers,
    resolve_circuit_breaker,
)

# =============================================================================
# CREATE CIRCUIT BREAKER EVENT TESTS
# =============================================================================


@pytest.mark.unit
class TestCreateCircuitBreakerEvent:
    """Unit tests for create_circuit_breaker_event with mocked database."""

    @patch("precog.database.crud_system.get_cursor")
    def test_create_event_returns_event_id(self, mock_get_cursor: MagicMock) -> None:
        """Test creating a circuit breaker event returns the new event_id."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"event_id": 42}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_circuit_breaker_event(
            breaker_type="data_stale",
            trigger_value={"component": "espn_api"},
            notes="ESPN poller went down",
        )

        assert result == 42
        mock_get_cursor.assert_called_once_with(commit=True)
        mock_cursor.execute.assert_called_once()

    @patch("precog.database.crud_system.get_cursor")
    def test_create_event_without_optional_params(self, mock_get_cursor: MagicMock) -> None:
        """Test creating event with only breaker_type (no trigger_value or notes)."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"event_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_circuit_breaker_event(breaker_type="manual")

        assert result == 1
        # Verify None passed for trigger_value and notes
        call_args = mock_cursor.execute.call_args[0]
        params = call_args[1]
        assert params[0] == "manual"
        assert params[1] is None  # trigger_value JSON
        assert params[2] is None  # notes

    @patch("precog.database.crud_system.get_cursor")
    def test_create_event_serializes_trigger_value(self, mock_get_cursor: MagicMock) -> None:
        """Test that trigger_value dict is serialized to JSON."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"event_id": 5}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        trigger = {"component": "kalshi_api", "error_count": 15}
        create_circuit_breaker_event(
            breaker_type="api_failures",
            trigger_value=trigger,
        )

        call_args = mock_cursor.execute.call_args[0]
        params = call_args[1]
        # trigger_value should be JSON-serialized
        parsed = json.loads(params[1])
        assert parsed["component"] == "kalshi_api"
        assert parsed["error_count"] == 15

    @patch("precog.database.crud_system.get_cursor")
    def test_create_event_returns_none_on_no_result(self, mock_get_cursor: MagicMock) -> None:
        """Test returns None if fetchone returns None (unexpected DB issue)."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_circuit_breaker_event(breaker_type="manual")

        assert result is None


# =============================================================================
# RESOLVE CIRCUIT BREAKER TESTS
# =============================================================================


@pytest.mark.unit
class TestResolveCircuitBreaker:
    """Unit tests for resolve_circuit_breaker with mocked database."""

    @patch("precog.database.crud_system.get_cursor")
    def test_resolve_active_breaker_returns_true(self, mock_get_cursor: MagicMock) -> None:
        """Test resolving an active breaker returns True."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = resolve_circuit_breaker(
            event_id=42,
            resolution_action="Service restarted",
        )

        assert result is True
        mock_get_cursor.assert_called_once_with(commit=True)

    @patch("precog.database.crud_system.get_cursor")
    def test_resolve_already_resolved_returns_false(self, mock_get_cursor: MagicMock) -> None:
        """Test resolving an already-resolved breaker returns False."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = resolve_circuit_breaker(event_id=999)

        assert result is False

    @patch("precog.database.crud_system.get_cursor")
    def test_resolve_without_action(self, mock_get_cursor: MagicMock) -> None:
        """Test resolving with no resolution_action passes None."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        resolve_circuit_breaker(event_id=10)

        call_args = mock_cursor.execute.call_args[0]
        params = call_args[1]
        assert params[0] is None  # resolution_action
        assert params[1] == 10  # event_id


# =============================================================================
# GET ACTIVE BREAKERS TESTS
# =============================================================================


@pytest.mark.unit
class TestGetActiveBreakers:
    """Unit tests for get_active_breakers with mocked database."""

    @patch("precog.database.crud_system.fetch_all")
    def test_get_all_active_breakers(self, mock_fetch_all: MagicMock) -> None:
        """Test fetching all active breakers without filter."""
        mock_fetch_all.return_value = [
            {"event_id": 1, "breaker_type": "data_stale"},
            {"event_id": 2, "breaker_type": "api_failures"},
        ]

        result = get_active_breakers()

        assert len(result) == 2
        assert result[0]["breaker_type"] == "data_stale"
        # Verify no params (no type filter)
        call_args = mock_fetch_all.call_args
        assert len(call_args[0]) == 1  # Just the query, no params

    @patch("precog.database.crud_system.fetch_all")
    def test_get_active_breakers_by_type(self, mock_fetch_all: MagicMock) -> None:
        """Test fetching active breakers filtered by type."""
        mock_fetch_all.return_value = [
            {"event_id": 1, "breaker_type": "data_stale"},
        ]

        result = get_active_breakers(breaker_type="data_stale")

        assert len(result) == 1
        # Verify type param was passed
        call_args = mock_fetch_all.call_args
        assert call_args[0][1] == ("data_stale",)

    @patch("precog.database.crud_system.fetch_all")
    def test_get_active_breakers_empty(self, mock_fetch_all: MagicMock) -> None:
        """Test returns empty list when no active breakers exist."""
        mock_fetch_all.return_value = []

        result = get_active_breakers()

        assert result == []
